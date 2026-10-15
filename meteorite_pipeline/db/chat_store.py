from typing import Any
from uuid import UUID, uuid4

from meteorite_pipeline.db.connection import get_chat_connection


def list_conversations(limit: int = 60) -> list[dict[str, Any]]:
    connection = get_chat_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, title, updated_at
                FROM public.chat_conversations
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (max(1, min(limit, 100)),),
            )
            return [
                {"id": str(row[0]), "title": row[1], "updated_at": row[2]}
                for row in cursor.fetchall()
            ]
    finally:
        connection.close()


def create_conversation() -> str:
    conversation_id = uuid4()
    connection = get_chat_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.chat_conversations (id, title) VALUES (%s, %s)",
                (conversation_id, "New conversation"),
            )
        connection.commit()
        return str(conversation_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_messages(conversation_id: str | UUID) -> list[dict[str, Any]]:
    connection = get_chat_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT role, content, created_at
                FROM public.chat_messages
                WHERE conversation_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (conversation_id, 100),
            )
            messages = [
                {"role": row[0], "content": row[1], "created_at": row[2]}
                for row in cursor.fetchall()
            ]
            return list(reversed(messages))
    finally:
        connection.close()


def add_message(conversation_id: str | UUID, role: str, content: str) -> None:
    if role not in {"user", "assistant"}:
        raise ValueError("Chat messages must have role 'user' or 'assistant'.")
    if not content.strip():
        raise ValueError("Chat message content cannot be empty.")

    connection = get_chat_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.chat_messages (conversation_id, role, content)
                VALUES (%s, %s, %s)
                """,
                (conversation_id, role, content),
            )
            if role == "user":
                cursor.execute(
                    """
                    UPDATE public.chat_conversations
                    SET title = CASE
                            WHEN title = 'New conversation' THEN %s
                            ELSE title
                        END,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (content.strip()[:72], conversation_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE public.chat_conversations
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (conversation_id,),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_conversation(conversation_id: str | UUID) -> None:
    connection = get_chat_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM public.chat_conversations WHERE id = %s",
                (conversation_id,),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()