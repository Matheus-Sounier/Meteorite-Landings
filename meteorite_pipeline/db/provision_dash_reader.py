import os

from psycopg import sql

from meteorite_pipeline.db.connection import get_connection


def provision_dash_reader() -> None:
    database_name = os.environ["POSTGRES_DB"]
    pipeline_user = os.environ["POSTGRES_USER"]
    dash_user = os.environ["DASH_DB_USER"]
    dash_password = os.environ["DASH_DB_PASSWORD"]

    if not dash_user or not dash_password:
        raise ValueError("DASH_DB_USER and DASH_DB_PASSWORD must be set.")
    if dash_user == pipeline_user:
        raise ValueError("DASH_DB_USER must differ from POSTGRES_USER.")

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (dash_user,))
            if cursor.fetchone() is not None:
                raise RuntimeError(
                    f"Role '{dash_user}' already exists; inspect its privileges before reuse."
                )

            cursor.execute(
                """
                SELECT
                    to_regclass('public.meteorite_landings') IS NOT NULL,
                    to_regclass('public.data_quality_report') IS NOT NULL
                """
            )
            if cursor.fetchone() != (True, True):
                raise RuntimeError(
                    "Run the pipeline once before provisioning the Dash reader role."
                )

            role = sql.Identifier(dash_user)
            cursor.execute(
                sql.SQL(
                    "CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}"
                ).format(role, sql.Literal(dash_password))
            )
            cursor.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(database_name), role
                )
            )
            cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
            cursor.execute(
                sql.SQL(
                    "GRANT SELECT ON TABLE public.meteorite_landings, "
                    "public.data_quality_report TO {}"
                ).format(role)
            )
            cursor.execute(
                sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(role)
            )
            cursor.execute(
                sql.SQL("ALTER ROLE {} IN DATABASE {} SET search_path = public").format(
                    role, sql.Identifier(database_name)
                )
            )
            cursor.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                    "GRANT SELECT ON TABLES TO {}"
                ).format(sql.Identifier(pipeline_user), role)
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> None:
    provision_dash_reader()
    print("Dash read-only role created with access to the analytics tables.")


if __name__ == "__main__":
    main()
