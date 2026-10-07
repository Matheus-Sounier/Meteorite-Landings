import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from meteorite_pipeline.application.orchestration import run_pipeline
from meteorite_pipeline.db.connection import get_connection
from meteorite_pipeline.db.schema import create_schema
from meteorite_pipeline.storage.output_writer import DatabaseWriteError


class PostgreSQLPipelineIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configured_database = os.environ.get("POSTGRES_DB")
        test_database = os.environ.get("POSTGRES_TEST_DB")
        if not test_database:
            raise unittest.SkipTest(
                "Set POSTGRES_TEST_DB to explicitly enable destructive database tests."
            )
        if test_database != configured_database:
            raise RuntimeError(
                "POSTGRES_TEST_DB must match POSTGRES_DB so the integration suite "
                "runs only against its explicitly selected test database."
            )

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
            cursor.execute(
                '''
                SELECT
                    pg_typeof("mass (g)")::text,
                    pg_typeof(year)::text,
                    pg_typeof(quality_any_issue)::text,
                    quality_invalid_latitude,
                    quality_longitude_outside_range,
                    quality_negative_mass,
                    quality_future_year
                FROM meteorite_landings
                WHERE id = %s
                ''',
                (2,),
            )
            stored_types_and_flags = cursor.fetchone()

        self.assertEqual(row_count, 2)
        self.assertEqual(flagged_count, 1)
        self.assertEqual(report_count, len(processed_data))
        self.assertEqual(report.loc[report["metric"] == "invalid_latitude", "value"].iloc[0], 1)
        self.assertEqual(
            stored_types_and_flags,
            ("double precision", "double precision", "boolean", True, True, True, True),
        )

    def test_pipeline_replaces_previous_database_load(self) -> None:
        self.write_source(self.source_rows)
        run_pipeline(self.csv_path)
        self.write_source(self.source_rows[:1])

        run_pipeline(self.csv_path)

        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*), MIN(id), MAX(id) FROM meteorite_landings")
            row_count, minimum_id, maximum_id = cursor.fetchone()

        self.assertEqual((row_count, minimum_id, maximum_id), (1, 1, 1))

    def test_schema_creation_is_idempotent(self) -> None:
        with get_connection() as connection, connection.cursor() as cursor:
            create_schema(cursor)
            create_schema(cursor)

        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.meteorite_landings')")
            self.assertEqual(cursor.fetchone()[0], "meteorite_landings")
            cursor.execute("SELECT to_regclass('public.data_quality_report')")
            self.assertEqual(cursor.fetchone()[0], "data_quality_report")

    def test_failed_load_rolls_back_truncate_and_preserves_previous_data(self) -> None:
        self.write_source(self.source_rows)
        run_pipeline(self.csv_path)

        constraint_name = "integration_reject_id_100"
        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"ALTER TABLE meteorite_landings "
                f"DROP CONSTRAINT IF EXISTS {constraint_name}"
            )
            cursor.execute(
                f"ALTER TABLE meteorite_landings "
                f"ADD CONSTRAINT {constraint_name} CHECK (id < 100)"
            )

        self.write_source([self.source_rows[0] | {"id": 100}])
        try:
            with self.assertRaises(DatabaseWriteError):
                run_pipeline(self.csv_path)
        finally:
            with get_connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    f"ALTER TABLE meteorite_landings "
                    f"DROP CONSTRAINT IF EXISTS {constraint_name}"
                )

        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM meteorite_landings")
            preserved_row_count = cursor.fetchone()[0]
            cursor.execute(
                "SELECT value FROM data_quality_report WHERE metric = %s",
                ("records_total",),
            )
            preserved_report_count = cursor.fetchone()[0]

        self.assertEqual(preserved_row_count, 2)
        self.assertEqual(preserved_report_count, 2)


if __name__ == "__main__":
    unittest.main()