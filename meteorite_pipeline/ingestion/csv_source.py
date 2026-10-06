from pathlib import Path

import pandas as pd


class CsvReadError(ValueError):
    """Raised when a source file exists but cannot be parsed as CSV."""


def load_csv(csv_path: Path) -> pd.DataFrame:
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    try:
        return pd.read_csv(csv_path)
    except (OSError, UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError) as error:
        raise CsvReadError(f"Could not read CSV '{csv_path}': {error}") from error