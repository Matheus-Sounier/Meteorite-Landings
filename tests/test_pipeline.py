import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd
import psycopg
from pandera.errors import SchemaErrors

from meteorite_pipeline.ingestion.csv_source import CsvReadError, load_csv
from meteorite_pipeline.application.orchestration import run_pipeline
from meteorite_pipeline.reporting.quality_report import build_quality_report
from meteorite_pipeline.storage.output_writer import DatabaseWriteError, write_to_database
from meteorite_pipeline.transformation.quality_flags import add_quality_flags, normalize_numeric_columns
from meteorite_pipeline.validation.schema import validate_dataset


class MeteoritePipelineTests(unittest.TestCase):
    def make_data(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "name": "Aachen",
                    "id": 1,
                    "nametype": "Valid",
                    "recclass": "L5",
                    "mass (g)": "21",
                    "fall": "Fell",
                    "year": "1880",
                    "reclat": "50.775",
                    "reclong": "6.08333",
                    "GeoLocation": "(50.775, 6.08333)",
                },
                {
                    "name": "Missing data",
                    "id": 2,
                    "nametype": "Valid",
                    "recclass": "H6",
                    "mass (g)": None,
                    "fall": "Found",
                    "year": None,
                    "reclat": None,
                    "reclong": None,
                    "GeoLocation": None,
                },
                {
                    "name": "Suspicious values",
                    "id": 3,
                    "nametype": "Valid",
                    "recclass": "L6",
                    "mass (g)": "-1",
                    "fall": "Found",
                    "year": "2101",
                    "reclat": "0",
                    "reclong": "0",
                    "GeoLocation": "(0, 0)",
                },
                {
                    "name": "Longitude edge",
                    "id": 3,
                    "nametype": "Valid",
                    "recclass": "L5",
                    "mass (g)": "not-a-number",
                    "fall": "Found",
                    "year": "1970",
                    "reclat": "0.5",
                    "reclong": "354.47333",
                    "GeoLocation": "(0.5, 354.47333)",
                },
            ]
        )

    def test_schema_rejects_missing_column(self) -> None:
        data, _ = normalize_numeric_columns(self.make_data())
        data = data.drop(columns="name")
        with self.assertRaises(SchemaErrors):
            validate_dataset(data)

    def test_missing_csv_raises_file_not_found(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            missing_path = Path(temporary_directory) / "missing.csv"
            with self.assertRaises(FileNotFoundError):
                load_csv(missing_path)

    def test_empty_csv_raises_read_error(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            empty_path = Path(temporary_directory) / "empty.csv"
            empty_path.write_text("", encoding="utf-8")
            with self.assertRaises(CsvReadError):
                load_csv(empty_path)

    def test_normalizes_numeric_values_and_marks_invalid_formats(self) -> None:
        data = pd.DataFrame(
            [
                {"mass (g)": "21.5", "year": "1880", "reclat": "50.1", "reclong": "-100"},
                {"mass (g)": None, "year": None, "reclat": None, "reclong": None},
                {
                    "mass (g)": "not-a-number",
                    "year": "unknown",
                    "reclat": "north",
                    "reclong": "west",
                },
            ]
        )

        normalized, invalid_numeric_format = normalize_numeric_columns(data)

        self.assertEqual(normalized.loc[0, "mass (g)"], 21.5)
        self.assertEqual(normalized.loc[0, "year"], 1880.0)
        self.assertTrue(normalized.loc[1].isna().all())
        self.assertTrue(normalized.loc[2].isna().all())
        self.assertEqual(invalid_numeric_format.tolist(), [False, False, True])

    def test_flags_suspicious_values_without_dropping_rows(self) -> None:
        data, invalid_numeric_format = normalize_numeric_columns(self.make_data())
        validated = validate_dataset(data)
        flagged = add_quality_flags(validated, invalid_numeric_format)
        report = build_quality_report(flagged).set_index("metric")["value"]

        self.assertEqual(len(flagged), 4)
        self.assertTrue(flagged.loc[1, "quality_missing_coordinates"])
        self.assertTrue(flagged.loc[2, "quality_zero_coordinates"])
        self.assertTrue(flagged.loc[2, "quality_future_year"])
        self.assertTrue(flagged.loc[2, "quality_negative_mass"])
        self.assertTrue(flagged.loc[3, "quality_longitude_outside_range"])
        self.assertTrue(flagged.loc[3, "quality_invalid_numeric_format"])
        self.assertTrue(flagged.loc[2:3, "quality_duplicate_id"].all())
        self.assertEqual(report["records_total"], 4)
        self.assertEqual(report["duplicate_id_rows"], 2)

    def test_flags_invalid_latitude_in_quality_report(self) -> None:
        data = self.make_data()
        data.loc[0, "reclat"] = "91"
        normalized, invalid_numeric_format = normalize_numeric_columns(data)

        flagged = add_quality_flags(validate_dataset(normalized), invalid_numeric_format)
        report = build_quality_report(flagged).set_index("metric")["value"]

        self.assertTrue(flagged.loc[0, "quality_invalid_latitude"])
        self.assertTrue(flagged.loc[0, "quality_any_issue"])
        self.assertEqual(report["invalid_latitude"], 1)

    def test_coordinate_boundaries_and_invalid_coordinate_cases(self) -> None:
        boundary_values = [
            (-90, -180),
            (90, 180),
            (90.01, 0),
            (0, -180.01),
            (None, 12),
            (0, 0),
        ]
        data = pd.concat(
            [self.make_data().iloc[[0]] for _ in boundary_values],
            ignore_index=True,
        )
        data["id"] = range(1, len(boundary_values) + 1)
        data["reclat"] = [latitude for latitude, _ in boundary_values]
        data["reclong"] = [longitude for _, longitude in boundary_values]
        normalized, invalid_numeric_format = normalize_numeric_columns(data)

        flagged = add_quality_flags(validate_dataset(normalized), invalid_numeric_format)

        self.assertFalse(flagged.loc[0, "quality_invalid_latitude"])
        self.assertFalse(flagged.loc[0, "quality_longitude_outside_range"])
        self.assertFalse(flagged.loc[1, "quality_invalid_latitude"])
        self.assertFalse(flagged.loc[1, "quality_longitude_outside_range"])
        self.assertTrue(flagged.loc[2, "quality_invalid_latitude"])
        self.assertTrue(flagged.loc[3, "quality_longitude_outside_range"])
        self.assertTrue(flagged.loc[4, "quality_missing_coordinates"])
        self.assertTrue(flagged.loc[5, "quality_zero_coordinates"])

    def test_quality_report_contains_every_metric(self) -> None:
        data, invalid_numeric_format = normalize_numeric_columns(self.make_data())
        flagged = add_quality_flags(validate_dataset(data), invalid_numeric_format)

        report = build_quality_report(flagged).set_index("metric")["value"]

        self.assertEqual(
            report.to_dict(),
            {
                "records_total": 4,
                "unique_ids": 3,
                "records_with_any_quality_flag": 3,
                "missing_mass": 2,
                "missing_year": 1,
                "missing_coordinates": 1,
                "zero_zero_coordinates": 1,
                "invalid_latitude": 0,
                "longitude_outside_minus180_180": 1,
                "future_year": 1,
                "negative_mass": 1,
                "duplicate_id_rows": 2,
                "invalid_numeric_format_rows": 1,
            },
        )

    def test_quality_report_returns_zero_metrics_for_empty_data(self) -> None:
        data, invalid_numeric_format = normalize_numeric_columns(self.make_data())
        flagged = add_quality_flags(validate_dataset(data), invalid_numeric_format)

        report = build_quality_report(flagged.iloc[:0]).set_index("metric")["value"]

        self.assertTrue(report.eq(0).all())
        self.assertEqual(len(report), 13)

    @patch("meteorite_pipeline.application.orchestration.write_to_database")
    @patch("meteorite_pipeline.application.orchestration.load_csv")
    def test_orchestration_sends_processed_data_and_report_to_database(
        self, load_csv_mock, write_to_database_mock
    ) -> None:
        source_data = self.make_data()
        load_csv_mock.return_value = source_data

        processed_data, report = run_pipeline(Path("source.csv"))

        self.assertEqual(len(processed_data), len(source_data))
        self.assertEqual(report.loc[0, "metric"], "records_total")
        write_to_database_mock.assert_called_once_with(processed_data, report)

    @patch("meteorite_pipeline.storage.output_writer.get_connection")
    def test_writes_processed_data_and_report_to_database(self, get_connection) -> None:
        data, invalid_numeric_format = normalize_numeric_columns(self.make_data())
        validated = validate_dataset(data)
        flagged = add_quality_flags(validated, invalid_numeric_format)
        report = build_quality_report(flagged)
        connection = get_connection.return_value
        cursor = connection.cursor.return_value.__enter__.return_value

        write_to_database(flagged, report)

        self.assertEqual(cursor.executemany.call_count, 2)
        data_rows = cursor.executemany.call_args_list[0].args[1]
        report_rows = cursor.executemany.call_args_list[1].args[1]
        self.assertEqual(len(data_rows), len(flagged))
        self.assertIsNone(data_rows[1][4])
        self.assertEqual(len(report_rows), len(report))
        cursor.execute.assert_any_call("TRUNCATE TABLE meteorite_landings, data_quality_report")
        connection.commit.assert_called_once_with()
        connection.close.assert_called_once_with()

    @patch("meteorite_pipeline.storage.output_writer.get_connection")
    def test_database_write_error_is_actionable(self, get_connection) -> None:
        data, invalid_numeric_format = normalize_numeric_columns(self.make_data())
        validated = validate_dataset(data)
        flagged = add_quality_flags(validated, invalid_numeric_format)
        report = build_quality_report(flagged)
        connection = get_connection.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.executemany.side_effect = psycopg.OperationalError("database unavailable")

        with self.assertRaises(DatabaseWriteError):
            write_to_database(flagged, report)

        connection.rollback.assert_called_once_with()
        connection.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()