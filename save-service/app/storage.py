from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from app.schemas import (
    SaveTurnRequest,
    SavedConversation,
    SavedMessage,
)


class ConversationNotFoundError(LookupError):
    pass


class ChatStore:
    def __init__(
        self,
        database_path: str,
        retention_days: int,
    ) -> None:
        self.database_path = database_path
        self.retention_days = retention_days

    def initialize(self) -> None:
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS conversations (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
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
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, request_id, role),
                    FOREIGN KEY(session_id)
                        REFERENCES conversations(session_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_conversations_expires_at
                    ON conversations(expires_at);

                CREATE INDEX IF NOT EXISTS idx_messages_session_created
                    ON messages(session_id, created_at);
                """
            )
            self._cleanup_expired(connection, self._now())

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
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
            created_at = (
                conversation["created_at"]
                if conversation is not None
                else self._to_text(saved_at)
            )

            connection.execute(
                """
                INSERT INTO conversations (
                    session_id,
                    created_at,
                    updated_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at
                """,
                (
                    session_id,
                    created_at,
                    self._to_text(saved_at),
                    self._to_text(expires_at),
                ),
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
                    self._to_text(saved_at),
                ),
                (
                    str(uuid4()),
                    session_id,
                    "assistant",
                    payload.assistant_message,
                    payload.risk_level,
                    payload.model,
                    payload.request_id,
                    self._to_text(saved_at),
                ),
            ]
            connection.executemany(
                """
                INSERT OR IGNORE INTO messages (
                    id,
                    session_id,
                    role,
                    content,
                    risk_level,
                    model,
                    request_id,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                message_rows,
            )

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
                WHERE session_id = ?
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
                WHERE session_id = ?
                ORDER BY created_at, rowid
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
                    created_at=self._from_text(message["created_at"]),
                )
                for message in messages
            ],
            created_at=self._from_text(conversation["created_at"]),
            updated_at=self._from_text(conversation["updated_at"]),
            expires_at=self._from_text(conversation["expires_at"]),
            retention_days=self.retention_days,
        )

    def delete_conversation(self, session_id: str) -> bool:
        with self._connect() as connection:
            result = connection.execute(
                "DELETE FROM conversations WHERE session_id = ?",
                (session_id,),
            )

        return result.rowcount > 0

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _cleanup_expired(
        self,
        connection: sqlite3.Connection,
        now: datetime,
    ) -> None:
        connection.execute(
            "DELETE FROM conversations WHERE expires_at <= ?",
            (self._to_text(now),),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _to_text(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _from_text(value: str) -> datetime:
        return datetime.fromisoformat(value)
