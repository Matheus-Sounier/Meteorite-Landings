from .connection import get_connection


def create_schema(cursor) -> None:
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS meteorite_landings (
            name TEXT NOT NULL,
            id BIGINT NOT NULL,
            nametype TEXT NOT NULL,
            recclass TEXT NOT NULL,
            "mass (g)" DOUBLE PRECISION,
            fall TEXT NOT NULL,
            year DOUBLE PRECISION,
            reclat DOUBLE PRECISION,
            reclong DOUBLE PRECISION,
            "GeoLocation" TEXT,
            quality_invalid_numeric_format BOOLEAN NOT NULL,
            quality_missing_mass BOOLEAN NOT NULL,
            quality_missing_year BOOLEAN NOT NULL,
            quality_missing_coordinates BOOLEAN NOT NULL,
            quality_zero_coordinates BOOLEAN NOT NULL,
            quality_invalid_latitude BOOLEAN NOT NULL,
            quality_longitude_outside_range BOOLEAN NOT NULL,
            quality_future_year BOOLEAN NOT NULL,
            quality_negative_mass BOOLEAN NOT NULL,
            quality_duplicate_id BOOLEAN NOT NULL,
            quality_any_issue BOOLEAN NOT NULL
        )
        '''
    )
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS data_quality_report (
            metric TEXT PRIMARY KEY,
            value BIGINT NOT NULL
        )
        '''
    )


def init_db() -> None:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            create_schema(cursor)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()