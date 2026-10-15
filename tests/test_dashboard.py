import json
import os
import unittest
from unittest.mock import patch

import psycopg

from meteorite_pipeline.dashboard.app import _chart_panel, _make_figures, create_app
from meteorite_pipeline.dashboard.queries import (
    MAP_POINT_LIMIT,
    _where_clause,
    load_dashboard_data,
)
from meteorite_pipeline.db.connection import get_dash_connection


def _empty_data() -> dict:
    return {
        "summary": {
            "total_records": 0,
            "unique_ids": 0,
            "fell_records": 0,
            "found_records": 0,
            "flagged_records": 0,
        },
        "by_year": [],
        "by_class": [],
        "map_points": [],
    }


def _dashboard_callback_payload(fall_type: str, include_flagged: bool) -> dict:
    return {
        "output": "..dashboard-content.children...globe-points.data..",
        "outputs": [
            {"id": "dashboard-content", "property": "children"},
            {"id": "globe-points", "property": "data"},
        ],
        "inputs": [
            {"id": "fall-filter", "property": "value", "value": fall_type},
            {"id": "include-flagged", "property": "checked", "value": include_flagged},
            {"id": "refresh-dashboard", "property": "n_clicks", "value": 0},
        ],
        "state": [],
        "changedPropIds": ["fall-filter.value"],
    }


class DashboardQueryTests(unittest.TestCase):
    def test_globe_sampling_limit_is_four_thousand(self) -> None:
        self.assertEqual(MAP_POINT_LIMIT, 4000)

    def test_filters_are_parameterized_and_exclude_flagged_by_default(self) -> None:
        where, parameters = _where_clause("Fell", include_flagged=False)

        self.assertEqual(parameters, ("Fell",))
        self.assertIn("fall = %s", where)
        self.assertIn("quality_any_issue = FALSE", where)

    def test_flagged_records_can_be_included_without_changing_parameters(self) -> None:
        where, parameters = _where_clause("Found", include_flagged=True)

        self.assertEqual(parameters, ("Found",))
        self.assertIn("fall = %s", where)
        self.assertNotIn("quality_any_issue", where)

    def test_invalid_fall_filter_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _where_clause("invalid' OR TRUE --", include_flagged=True)

    def test_all_fall_filter_does_not_add_sql_parameters(self) -> None:
        where, parameters = _where_clause("all", include_flagged=True)

        self.assertEqual(where, "TRUE")
        self.assertEqual(parameters, ())


class DashboardFigureTests(unittest.TestCase):
    def test_empty_results_produce_three_annotated_chart_figures(self) -> None:
        figures = _make_figures(_empty_data())

        self.assertEqual(len(figures), 3)
        for figure in figures:
            self.assertEqual(figure.layout.annotations[0].text, "No records for this filter")

    def test_chart_component_uses_figure_height(self) -> None:
        for figure in _make_figures(_empty_data()):
            with self.subTest(height=figure.layout.height):
                graph = _chart_panel("Chart", "Subtitle", figure).children[1]
                self.assertEqual(graph.style["height"], f"{figure.layout.height}px")

    def test_populated_results_produce_all_figure_types(self) -> None:
        data = {
            "summary": {
                "total_records": 1,
                "unique_ids": 1,
                "fell_records": 1,
                "found_records": 0,
                "flagged_records": 0,
            },
            "by_year": [{"year": 1880, "records": 1}],
            "by_class": [{"recclass": "L5", "records": 1}],
            "map_points": [{
                "name": "Aachen",
                "id": 1,
                "recclass": "L5",
                "fall": "Fell",
                "mass_g": 21.0,
                "reclat": 50.775,
                "reclong": 6.08333,
            }],
        }

        figures = _make_figures(data)

        self.assertEqual(len(figures), 3)
        self.assertTrue(all(figure.data for figure in figures))


class DashboardAppTests(unittest.TestCase):
    def test_layout_endpoint_renders_without_querying_database(self) -> None:
        app = create_app()
        client = app.server.test_client()

        with patch("meteorite_pipeline.dashboard.app.load_dashboard_data") as load_data:
            response = client.get("/_dash-layout")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Meteorite landings", response.data)
        load_data.assert_not_called()

    def test_callback_renders_empty_state_and_passes_filters(self) -> None:
        app = create_app()
        client = app.server.test_client()

        with patch("meteorite_pipeline.dashboard.app.load_dashboard_data", return_value=_empty_data()) as load_data:
            response = client.post(
                "/_dash-update-component",
                json=_dashboard_callback_payload("Fell", True),
            )

        self.assertEqual(response.status_code, 200)
        load_data.assert_called_once_with("Fell", True)
        serialized = json.dumps(response.get_json())
        self.assertIn("No records for this filter", serialized)

    def test_callback_returns_visible_error_when_database_is_unavailable(self) -> None:
        app = create_app()
        client = app.server.test_client()

        with patch(
            "meteorite_pipeline.dashboard.app.load_dashboard_data",
            side_effect=ConnectionError("database unavailable"),
        ):
            response = client.post(
                "/_dash-update-component",
                json=_dashboard_callback_payload("all", False),
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Database unavailable", response.data)


class DashboardPostgreSQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configured_database = os.environ.get("POSTGRES_DB")
        test_database = os.environ.get("DASH_TEST_DB")
        if not test_database:
            raise unittest.SkipTest(
                "Set DASH_TEST_DB to POSTGRES_DB to enable read-only dashboard integration tests."
            )
        if test_database != configured_database:
            raise RuntimeError(
                "DASH_TEST_DB must match POSTGRES_DB to explicitly select the integration database."
            )
        try:
            connection = get_dash_connection()
        except psycopg.OperationalError as error:
            if error.sqlstate is not None:
                raise
            raise unittest.SkipTest(
                "PostgreSQL is unreachable; dashboard integration tests were skipped."
            ) from error
        else:
            connection.close()

    def test_dash_reader_returns_consistent_persisted_data(self) -> None:
        data = load_dashboard_data()
        summary = data["summary"]

        self.assertGreater(summary["total_records"], 0)
        self.assertEqual(summary["flagged_records"], 0)
        self.assertEqual(
            summary["total_records"],
            summary["fell_records"] + summary["found_records"],
        )
        self.assertLessEqual(len(data["map_points"]), MAP_POINT_LIMIT)
        for point in data["map_points"]:
            self.assertTrue(-90 <= point["reclat"] <= 90)
            self.assertTrue(-180 <= point["reclong"] <= 180)
            self.assertFalse(point["reclat"] == 0 and point["reclong"] == 0)

    def test_fall_filters_do_not_mix_record_types(self) -> None:
        for fall_type, expected_fell, expected_found in (
            ("Fell", True, False),
            ("Found", False, True),
        ):
            with self.subTest(fall_type=fall_type):
                summary = load_dashboard_data(fall_type)["summary"]
                self.assertGreater(summary["total_records"], 0)
                self.assertEqual(summary["fell_records"] > 0, expected_fell)
                self.assertEqual(summary["found_records"] > 0, expected_found)


if __name__ == "__main__":
    unittest.main()
