import pandera.pandas as pa
import pandas as pd


DATASET_SCHEMA = pa.DataFrameSchema(
    {
        "name": pa.Column(str, nullable=False),
        "id": pa.Column(int, nullable=False),
        "nametype": pa.Column(str, nullable=False),
        "recclass": pa.Column(str, nullable=False),
        "mass (g)": pa.Column(float, nullable=True),
        "fall": pa.Column(str, nullable=False),
        "year": pa.Column(float, nullable=True),
        "reclat": pa.Column(float, nullable=True),
        "reclong": pa.Column(float, nullable=True),
        "GeoLocation": pa.Column(str, nullable=True, required=False),
    },
    strict=True,
)


def validate_dataset(data: pd.DataFrame) -> pd.DataFrame:
    return DATASET_SCHEMA.validate(data, lazy=True)