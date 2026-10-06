from datetime import datetime

import pandas as pd


NUMERIC_COLUMNS = ["mass (g)", "year", "reclat", "reclong"]


def normalize_numeric_columns(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    normalized = data.copy()
    original_numeric = normalized[NUMERIC_COLUMNS].copy()

    for column in NUMERIC_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    invalid_numeric_format = (
        original_numeric.notna() & normalized[NUMERIC_COLUMNS].isna()
    ).any(axis=1).rename("quality_invalid_numeric_format")
    return normalized, invalid_numeric_format


def add_quality_flags(data: pd.DataFrame, invalid_numeric_format: pd.Series) -> pd.DataFrame:
    flagged = data.copy()
    flagged["quality_invalid_numeric_format"] = invalid_numeric_format
    flagged["quality_missing_mass"] = flagged["mass (g)"].isna()
    flagged["quality_missing_year"] = flagged["year"].isna()
    flagged["quality_missing_coordinates"] = flagged[["reclat", "reclong"]].isna().any(axis=1)
    flagged["quality_zero_coordinates"] = flagged["reclat"].eq(0) & flagged["reclong"].eq(0)
    flagged["quality_invalid_latitude"] = flagged["reclat"].notna() & ~flagged["reclat"].between(-90, 90)
    flagged["quality_longitude_outside_range"] = (
        flagged["reclong"].notna() & ~flagged["reclong"].between(-180, 180)
    )
    flagged["quality_future_year"] = flagged["year"].notna() & flagged["year"].gt(datetime.now().year)
    flagged["quality_negative_mass"] = flagged["mass (g)"].notna() & flagged["mass (g)"].lt(0)
    flagged["quality_duplicate_id"] = flagged["id"].duplicated(keep=False)

    quality_columns = [column for column in flagged if column.startswith("quality_")]
    flagged["quality_any_issue"] = flagged[quality_columns].any(axis=1)
    return flagged