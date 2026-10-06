from pathlib import Path

import pandas as pd

from meteorite_pipeline.ingestion.csv_source import load_csv
from meteorite_pipeline.reporting.quality_report import build_quality_report
from meteorite_pipeline.storage.output_writer import write_to_database
from meteorite_pipeline.transformation.quality_flags import add_quality_flags, normalize_numeric_columns
from meteorite_pipeline.validation.schema import validate_dataset


def run_pipeline(
    csv_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_data = load_csv(csv_path)
    normalized_data, invalid_numeric_format = normalize_numeric_columns(raw_data)
    validated_data = validate_dataset(normalized_data)
    processed_data = add_quality_flags(validated_data, invalid_numeric_format)
    report = build_quality_report(processed_data)
    write_to_database(processed_data, report)
    return processed_data, report