import pandas as pd
import psycopg
from psycopg import sql

from meteorite_pipeline.db.connection import get_connection
from meteorite_pipeline.db.schema import create_schema


class DatabaseWriteError(RuntimeError):
    """Raised when processed data cannot be stored in PostgreSQL."""


def _insert_statement(table_name: str, columns: list[str]) -> sql.Composed:
    identifiers = sql.SQL(", ").join(sql.Identifier(column) for column in columns)
    placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in columns)
    return sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table_name), identifiers, placeholders
    )


def _database_value(value: object) -> object:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _records(data: pd.DataFrame) -> list[tuple[object, ...]]:
    return [
        tuple(_database_value(value) for value in row)
        for row in data.itertuples(index=False, name=None)
    ]


def write_to_database(data: pd.DataFrame, report: pd.DataFrame) -> None:
    connection = None
    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            create_schema(cursor)
            cursor.execute("TRUNCATE TABLE meteorite_landings, data_quality_report")
            cursor.executemany(
                _insert_statement("meteorite_landings", list(data.columns)),
                _records(data),
            )
            cursor.executemany(
                _insert_statement("data_quality_report", list(report.columns)),
                _records(report),
            )
        connection.commit()
    except Exception as error:
        if connection is not None:
            connection.rollback()
        if isinstance(error, psycopg.Error):
            raise DatabaseWriteError(f"Could not write pipeline results to PostgreSQL: {error}") from error
        raise
    finally:
        if connection is not None:
            connection.close()