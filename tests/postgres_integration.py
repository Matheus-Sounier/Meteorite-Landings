import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from meteorite_pipeline.application.orchestration import run_pipeline
from meteorite_pipeline.db.connection import get_connection


class PostgreSQLPipelineIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.csv_path = Path(self.temporary_directory.name) / "meteorites.csv"
        self.source_rows = [
            {
                "name": "Aachen",
                "id": 1,
                "nametype": "Valid",
                "recclass": "L5",
                "mass (g)": 21.0,
                "fall": "Fell",
                "year": 1880.0,
                "reclat": 50.775,
                "reclong": 6.08333,
                "GeoLocation": "(50.775, 6.08333)",
            },
            {
                "name": "Suspicious sample",
                "id": 2,
                "nametype": "Valid",
                "recclass": "L6",
                "mass (g)": -1.0,
                "fall": "Found",
                "year": 2101.0,
                "reclat": 91,
                "reclong": 181,
                "GeoLocation": "(91, 181)",
            },
        ]

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_source(self, rows: list[dict[str, object]]) -> None:
        pd.DataFrame(rows).to_csv(self.csv_path, index=False)

    def test_pipeline_persists_rows_flags_and_quality_report(self) -> None:
        self.write_source(self.source_rows)

        processed_data, report = run_pipeline(self.csv_path)

        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*), COUNT(*) FILTER (WHERE quality_any_issue)
                FROM meteorite_landings
                """
            )
            row_count, flagged_count = cursor.fetchone()
            cursor.execute(
                "SELECT value FROM data_quality_report WHERE metric = %s",
                ("records_total",),
            )
            report_count = cursor.fetchone()[0]

        self.assertEqual(row_count, 2)
        self.assertEqual(flagged_count, 1)
        self.assertEqual(report_count, len(processed_data))
        self.assertEqual(report.loc[report["metric"] == "invalid_latitude", "value"].iloc[0], 1)

    def test_pipeline_replaces_previous_database_load(self) -> None:
        self.write_source(self.source_rows)
        run_pipeline(self.csv_path)
        self.write_source(self.source_rows[:1])

        run_pipeline(self.csv_path)

        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*), MIN(id), MAX(id) FROM meteorite_landings")
            row_count, minimum_id, maximum_id = cursor.fetchone()

        self.assertEqual((row_count, minimum_id, maximum_id), (1, 1, 1))


if __name__ == "__main__":
    unittest.main()