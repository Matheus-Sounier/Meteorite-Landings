import os

from psycopg import sql

from meteorite_pipeline.db.connection import get_connection


def provision_chat_store() -> None:
    database_name = os.environ["POSTGRES_DB"]
    pipeline_user = os.environ["POSTGRES_USER"]
    dash_user = os.environ["DASH_DB_USER"]
    chat_user = os.environ["CHAT_DB_USER"]
    chat_password = os.environ["CHAT_DB_PASSWORD"]

    if not chat_user or not chat_password:
        raise ValueError("CHAT_DB_USER and CHAT_DB_PASSWORD must be set.")
    if chat_user in {pipeline_user, dash_user}:
        raise ValueError("CHAT_DB_USER must differ from POSTGRES_USER and DASH_DB_USER.")

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (chat_user,))
            if cursor.fetchone() is not None:
                raise RuntimeError(
                    f"Role '{chat_user}' already exists; inspect its privileges before reuse."
                )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.chat_conversations (
                    id UUID PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.chat_messages (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    conversation_id UUID NOT NULL REFERENCES public.chat_conversations(id)
                        ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            role = sql.Identifier(chat_user)
            cursor.execute(
                sql.SQL(
                    "CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}"
                ).format(role, sql.Literal(chat_password))
            )
            cursor.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(database_name), role
                )
            )
            cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
            cursor.execute(
                sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "
                    "public.chat_conversations, public.chat_messages TO {}"
                ).format(role)
            )
            cursor.execute(
                sql.SQL("GRANT USAGE, SELECT ON SEQUENCE public.chat_messages_id_seq TO {}").format(
                    role
                )
            )
            cursor.execute(
                sql.SQL("ALTER ROLE {} IN DATABASE {} SET search_path = public").format(
                    role, sql.Identifier(database_name)
                )
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> None:
    provision_chat_store()
    print("Chat history tables created with a dedicated role.")


if __name__ == "__main__":
    main()