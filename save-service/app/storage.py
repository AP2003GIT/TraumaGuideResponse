from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from app.schemas import (
    SaveTurnRequest,
    SavedConversation,
    SavedConversationList,
    SavedMessage,
    SavedConversationSummary,
)


class ConversationNotFoundError(LookupError):
    pass


class ChatStore:
    def __init__(
        self,
        database_url: str,
        retention_days: int,
        max_saved_chats: int,
    ) -> None:
        self.database_url = database_url
        self.retention_days = retention_days
        self.max_saved_chats = max_saved_chats

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    session_id TEXT PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    expires_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL
                        REFERENCES conversations(session_id)
                        ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK (
                        role IN ('user', 'assistant')
                    ),
                    content TEXT NOT NULL,
                    risk_level TEXT CHECK (
                        risk_level IN (
                            'standard',
                            'elevated',
                            'high',
                            'immediate'
                        )
                    ),
                    model TEXT,
                    request_id TEXT NOT NULL,
                    turn_position SMALLINT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    UNIQUE(session_id, request_id, role)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversations_expires_at
                    ON conversations(expires_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversations_updated_at
                    ON conversations(updated_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_session_created
                    ON messages(session_id, created_at, turn_position)
                """
            )
            self._cleanup_expired(connection, self._now())
            self._prune_oldest(connection)

    def health_check(self) -> None:
        with self._connect() as connection:
            connection.execute("SELECT 1")

    def save_turn(
        self,
        session_id: str,
        payload: SaveTurnRequest,
        *,
        now: datetime | None = None,
    ) -> SavedConversation:
        saved_at = now or self._now()
        expires_at = saved_at + timedelta(days=self.retention_days)

        with self._connect() as connection:
            self._cleanup_expired(connection, saved_at)

            conversation = connection.execute(
                """
                SELECT created_at
                FROM conversations
                WHERE session_id = %s
                """,
                (session_id,),
            ).fetchone()
            created_at = (
                conversation["created_at"]
                if conversation is not None
                else saved_at
            )

            connection.execute(
                """
                INSERT INTO conversations (
                    session_id,
                    created_at,
                    updated_at,
                    expires_at
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(session_id) DO UPDATE SET
                    updated_at = EXCLUDED.updated_at,
                    expires_at = EXCLUDED.expires_at
                """,
                (session_id, created_at, saved_at, expires_at),
            )

            message_rows = [
                (
                    str(uuid4()),
                    session_id,
                    "user",
                    payload.user_message,
                    None,
                    None,
                    payload.request_id,
                    0,
                    saved_at,
                ),
                (
                    str(uuid4()),
                    session_id,
                    "assistant",
                    payload.assistant_message,
                    payload.risk_level,
                    payload.model,
                    payload.request_id,
                    1,
                    saved_at,
                ),
            ]
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO messages (
                        id,
                        session_id,
                        role,
                        content,
                        risk_level,
                        model,
                        request_id,
                        turn_position,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(session_id, request_id, role) DO NOTHING
                    """,
                    message_rows,
                )

            self._prune_oldest(connection)

        return self.get_conversation(session_id, now=saved_at)

    def get_conversation(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> SavedConversation:
        checked_at = now or self._now()

        with self._connect() as connection:
            self._cleanup_expired(connection, checked_at)

            conversation = connection.execute(
                """
                SELECT session_id, created_at, updated_at, expires_at
                FROM conversations
                WHERE session_id = %s
                """,
                (session_id,),
            ).fetchone()

            if conversation is None:
                raise ConversationNotFoundError(session_id)

            messages = connection.execute(
                """
                SELECT
                    id,
                    role,
                    content,
                    risk_level,
                    model,
                    request_id,
                    created_at
                FROM messages
                WHERE session_id = %s
                ORDER BY created_at, request_id, turn_position
                """,
                (session_id,),
            ).fetchall()

        return SavedConversation(
            session_id=conversation["session_id"],
            messages=[
                SavedMessage(
                    id=message["id"],
                    role=message["role"],
                    content=message["content"],
                    risk_level=message["risk_level"],
                    model=message["model"],
                    request_id=message["request_id"],
                    created_at=self._ensure_utc(message["created_at"]),
                )
                for message in messages
            ],
            created_at=self._ensure_utc(conversation["created_at"]),
            updated_at=self._ensure_utc(conversation["updated_at"]),
            expires_at=self._ensure_utc(conversation["expires_at"]),
            retention_days=self.retention_days,
        )

    def list_conversations(
        self,
        *,
        now: datetime | None = None,
    ) -> SavedConversationList:
        checked_at = now or self._now()

        with self._connect() as connection:
            self._cleanup_expired(connection, checked_at)
            self._prune_oldest(connection)

            conversations = connection.execute(
                """
                SELECT
                    c.session_id,
                    c.created_at,
                    c.updated_at,
                    c.expires_at,
                    COUNT(m.id)::INTEGER AS message_count,
                    COALESCE(
                        (
                            SELECT LEFT(user_message.content, 120)
                            FROM messages AS user_message
                            WHERE
                                user_message.session_id = c.session_id
                                AND user_message.role = 'user'
                            ORDER BY
                                user_message.created_at,
                                user_message.request_id,
                                user_message.turn_position
                            LIMIT 1
                        ),
                        'Untitled chat'
                    ) AS title,
                    COALESCE(
                        (
                            SELECT LEFT(last_message.content, 180)
                            FROM messages AS last_message
                            WHERE last_message.session_id = c.session_id
                            ORDER BY
                                last_message.created_at DESC,
                                last_message.request_id DESC,
                                last_message.turn_position DESC
                            LIMIT 1
                        ),
                        ''
                    ) AS last_message_preview
                FROM conversations AS c
                LEFT JOIN messages AS m
                    ON m.session_id = c.session_id
                GROUP BY
                    c.session_id,
                    c.created_at,
                    c.updated_at,
                    c.expires_at
                ORDER BY c.updated_at DESC, c.session_id DESC
                LIMIT %s
                """,
                (self.max_saved_chats,),
            ).fetchall()

        return SavedConversationList(
            conversations=[
                SavedConversationSummary(
                    session_id=conversation["session_id"],
                    title=conversation["title"],
                    last_message_preview=(
                        conversation["last_message_preview"]
                    ),
                    message_count=conversation["message_count"],
                    created_at=self._ensure_utc(
                        conversation["created_at"]
                    ),
                    updated_at=self._ensure_utc(
                        conversation["updated_at"]
                    ),
                    expires_at=self._ensure_utc(
                        conversation["expires_at"]
                    ),
                    retention_days=self.retention_days,
                )
                for conversation in conversations
            ],
            max_saved_chats=self.max_saved_chats,
            retention_days=self.retention_days,
        )

    def delete_conversation(self, session_id: str) -> bool:
        with self._connect() as connection:
            result = connection.execute(
                "DELETE FROM conversations WHERE session_id = %s",
                (session_id,),
            )

        return result.rowcount > 0

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def _cleanup_expired(
        self,
        connection: psycopg.Connection,
        now: datetime,
    ) -> None:
        connection.execute(
            "DELETE FROM conversations WHERE expires_at <= %s",
            (now,),
        )

    def _prune_oldest(self, connection: psycopg.Connection) -> None:
        connection.execute(
            """
            DELETE FROM conversations
            WHERE session_id IN (
                SELECT session_id
                FROM conversations
                ORDER BY updated_at DESC, session_id DESC
                OFFSET %s
            )
            """,
            (self.max_saved_chats,),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)
