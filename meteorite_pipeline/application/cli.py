import argparse
from pathlib import Path

from pandera.errors import SchemaErrors

from meteorite_pipeline.application.orchestration import run_pipeline
from meteorite_pipeline.ingestion.csv_source import CsvReadError
from meteorite_pipeline.storage.output_writer import DatabaseWriteError


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile and validate meteorite landing data.")
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "Meteorite_Landings.csv",
        help="Path to the source CSV.",
    )
    args = parser.parse_args()

    if not args.csv_path.is_file():
        parser.error(f"CSV file not found: {args.csv_path}")

    try:
        data, report = run_pipeline(args.csv_path)
    except (CsvReadError, FileNotFoundError, DatabaseWriteError, SchemaErrors) as error:
        parser.exit(2, f"Pipeline failed: {error}\n")

    source_column_count = sum(not column.startswith("quality_") for column in data.columns)

    print("=== Meteorite Landings: pandas + Pandera + PostgreSQL ===")
    print(f"Source: {args.csv_path}")
    print(f"Records: {len(data):,}")
    print(f"Columns: {source_column_count} source + quality flags")
    print("\nPandera schema: passed")
    print("\nQuality checks:")
    print(report.to_string(index=False))
    print("\nRecords by fall type:")
    print(data["fall"].value_counts(dropna=False).to_string())
    print("\nTop 5 classes:")
    print(data["recclass"].value_counts().head(5).to_string())
    print("\nMass (g):")
    print(data["mass (g)"].describe(percentiles=[0.5, 0.9, 0.99]).to_string())
    print("\nPostgreSQL tables updated:")
    print("- meteorite_landings (Tableau dataset)")
    print("- data_quality_report")


if __name__ == "__main__":
    main()