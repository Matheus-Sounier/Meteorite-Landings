import pandas as pd


def build_quality_report(data: pd.DataFrame) -> pd.DataFrame:
    report_values = {
        "records_total": len(data),
        "unique_ids": data["id"].nunique(),
        "records_with_any_quality_flag": int(data["quality_any_issue"].sum()),
        "missing_mass": int(data["quality_missing_mass"].sum()),
        "missing_year": int(data["quality_missing_year"].sum()),
        "missing_coordinates": int(data["quality_missing_coordinates"].sum()),
        "zero_zero_coordinates": int(data["quality_zero_coordinates"].sum()),
        "invalid_latitude": int(data["quality_invalid_latitude"].sum()),
        "longitude_outside_minus180_180": int(data["quality_longitude_outside_range"].sum()),
        "future_year": int(data["quality_future_year"].sum()),
        "negative_mass": int(data["quality_negative_mass"].sum()),
        "duplicate_id_rows": int(data["quality_duplicate_id"].sum()),
        "invalid_numeric_format_rows": int(data["quality_invalid_numeric_format"].sum()),
    }
    return pd.DataFrame(report_values.items(), columns=["metric", "value"])