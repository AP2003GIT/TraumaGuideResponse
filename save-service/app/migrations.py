from __future__ import annotations

from collections.abc import Sequence

import psycopg


Migration = tuple[str, Sequence[str]]


MIGRATIONS: Sequence[Migration] = (
    (
        "001_initial_storage_schema",
        (
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMPTZ NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS conversations (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL
            )
            """,
            "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS user_id TEXT",
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
            """,
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,
                created_at TIMESTAMPTZ NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                used_at TIMESTAMPTZ
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
            """
            CREATE INDEX IF NOT EXISTS idx_conversations_expires_at
                ON conversations(expires_at)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
                ON conversations(user_id, updated_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_messages_session_created
                ON messages(session_id, created_at, turn_position)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user
                ON password_reset_tokens(user_id, expires_at)
            """,
        ),
    ),
    (
        "002_user_roles",
        (
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user'
            """,
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'users_role_check'
                ) THEN
                    ALTER TABLE users
                    ADD CONSTRAINT users_role_check
                    CHECK (role IN ('user', 'admin'));
                END IF;
            END
            $$;
            """,
        ),
    ),
)


def run_migrations(connection: psycopg.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    applied = {
        row["version"]
        for row in connection.execute(
            "SELECT version FROM schema_migrations"
        ).fetchall()
    }

    for version, statements in MIGRATIONS:
        if version in applied:
            continue

        for statement in statements:
            connection.execute(statement)

        connection.execute(
            "INSERT INTO schema_migrations (version) VALUES (%s)",
            (version,),
        )
