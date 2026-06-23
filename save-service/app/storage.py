from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from app.schemas import (
    AccountExport,
    AdminSummary,
    AuthRequest,
    AuthenticatedUser,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetRequestResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    SaveTurnRequest,
    SavedConversation,
    SavedConversationList,
    SavedConversationSummary,
    SavedMessage,
)
from app.migrations import run_migrations


class AccountAlreadyExistsError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


class InvalidResetTokenError(ValueError):
    pass


class UserNotFoundError(LookupError):
    pass


class ConversationNotFoundError(LookupError):
    pass


class ChatStore:
    def __init__(
        self,
        database_url: str,
        retention_days: int,
        max_saved_chats: int,
        admin_emails: list[str] | None = None,
    ) -> None:
        self.database_url = database_url
        self.retention_days = retention_days
        self.max_saved_chats = max_saved_chats
        self.admin_emails = {
            email.strip().lower()
            for email in (admin_emails or [])
            if email.strip()
        }

    def initialize(self) -> None:
        with self._connect() as connection:
            run_migrations(connection)
            self._cleanup_expired(connection, self._now())
            self._cleanup_reset_tokens(connection, self._now())

    def health_check(self) -> None:
        with self._connect() as connection:
            connection.execute("SELECT 1")

    def _role_for_email(self, email: str, stored_role: str = "user") -> str:
        if email.strip().lower() in self.admin_emails:
            return "admin"
        if stored_role == "admin":
            return "admin"
        return "user"

    def _user_from_row(self, row) -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id=row["user_id"],
            email=row["email"],
            display_name=row["display_name"],
            role=self._role_for_email(
                row["email"],
                row["role"] if "role" in row else "user",
            ),
        )

    def create_user(self, payload: RegisterRequest) -> AuthenticatedUser:
        now = self._now()
        user = AuthenticatedUser(
            user_id=str(uuid4()),
            email=payload.email,
            display_name=payload.display_name,
            role=self._role_for_email(payload.email),
        )

        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO users (
                        user_id,
                        email,
                        display_name,
                        password_hash,
                        role,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user.user_id,
                        user.email,
                        user.display_name,
                        self._hash_password(payload.password),
                        user.role,
                        now,
                    ),
                )
        except psycopg.errors.UniqueViolation as exc:
            raise AccountAlreadyExistsError(payload.email) from exc

        return user

    def authenticate_user(self, payload: AuthRequest) -> AuthenticatedUser:
        with self._connect() as connection:
            user = connection.execute(
                """
                SELECT user_id, email, display_name, password_hash, role
                FROM users
                WHERE email = %s
                """,
                (payload.email,),
            ).fetchone()

        if user is None or not self._verify_password(
            payload.password,
            user["password_hash"],
        ):
            raise InvalidCredentialsError("Invalid email or password.")

        return self._user_from_row(user)

    def get_user(self, user_id: str) -> AuthenticatedUser:
        with self._connect() as connection:
            user = connection.execute(
                """
                SELECT user_id, email, display_name, role
                FROM users
                WHERE user_id = %s
                """,
                (user_id,),
            ).fetchone()

        if user is None:
            raise UserNotFoundError(user_id)

        return self._user_from_row(user)

    def update_user_profile(
        self,
        user_id: str,
        payload: ProfileUpdateRequest,
    ) -> AuthenticatedUser:
        with self._connect() as connection:
            user = connection.execute(
                """
                SELECT user_id, password_hash
                FROM users
                WHERE user_id = %s
                """,
                (user_id,),
            ).fetchone()
            if user is None:
                raise UserNotFoundError(user_id)

            password_hash = user["password_hash"]
            if payload.new_password:
                if not payload.current_password or not self._verify_password(
                    payload.current_password,
                    password_hash,
                ):
                    raise InvalidCredentialsError(
                        "Current password is required.",
                    )
                password_hash = self._hash_password(payload.new_password)

            try:
                updated = connection.execute(
                    """
                    UPDATE users
                    SET
                        display_name = %s,
                        email = %s,
                        role = %s,
                        password_hash = %s
                    WHERE user_id = %s
                    RETURNING user_id, email, display_name, role
                    """,
                    (
                        payload.display_name,
                        payload.email,
                        self._role_for_email(payload.email),
                        password_hash,
                        user_id,
                    ),
                ).fetchone()
            except psycopg.errors.UniqueViolation as exc:
                raise AccountAlreadyExistsError(payload.email) from exc

        if updated is None:
            raise UserNotFoundError(user_id)

        return self._user_from_row(updated)

    def request_password_reset(
        self,
        payload: PasswordResetRequest,
    ) -> PasswordResetRequestResponse:
        now = self._now()
        token = secrets.token_urlsafe(32)

        with self._connect() as connection:
            self._cleanup_reset_tokens(connection, now)
            user = connection.execute(
                """
                SELECT user_id
                FROM users
                WHERE email = %s
                """,
                (payload.email,),
            ).fetchone()

            if user is None:
                return PasswordResetRequestResponse(
                    accepted=True,
                    dev_reset_token=None,
                )

            connection.execute(
                """
                INSERT INTO password_reset_tokens (
                    token_hash,
                    user_id,
                    created_at,
                    expires_at,
                    used_at
                )
                VALUES (%s, %s, %s, %s, NULL)
                """,
                (
                    self._hash_reset_token(token),
                    user["user_id"],
                    now,
                    now + timedelta(minutes=30),
                ),
            )

        return PasswordResetRequestResponse(
            accepted=True,
            dev_reset_token=token,
        )

    def confirm_password_reset(
        self,
        payload: PasswordResetConfirmRequest,
    ) -> AuthenticatedUser:
        now = self._now()
        token_hash = self._hash_reset_token(payload.reset_token)

        with self._connect() as connection:
            token = connection.execute(
                """
                SELECT token_hash, user_id
                FROM password_reset_tokens
                WHERE
                    token_hash = %s
                    AND used_at IS NULL
                    AND expires_at > %s
                """,
                (token_hash, now),
            ).fetchone()

            if token is None:
                raise InvalidResetTokenError("Invalid reset token.")

            updated = connection.execute(
                """
                UPDATE users
                SET password_hash = %s
                WHERE user_id = %s
                RETURNING user_id, email, display_name, role
                """,
                (
                    self._hash_password(payload.new_password),
                    token["user_id"],
                ),
            ).fetchone()
            connection.execute(
                """
                UPDATE password_reset_tokens
                SET used_at = %s
                WHERE token_hash = %s
                """,
                (now, token_hash),
            )

        if updated is None:
            raise InvalidResetTokenError("Invalid reset token.")

        return self._user_from_row(updated)

    def save_turn(
        self,
        user_id: str,
        session_id: str,
        payload: SaveTurnRequest,
        *,
        now: datetime | None = None,
    ) -> SavedConversation:
        saved_at = now or self._now()
        expires_at = saved_at + timedelta(days=self.retention_days)

        with self._connect() as connection:
            self._cleanup_expired(connection, saved_at)
            self._ensure_user_exists(connection, user_id)

            conversation = connection.execute(
                """
                SELECT created_at, user_id
                FROM conversations
                WHERE session_id = %s
                """,
                (session_id,),
            ).fetchone()
            if (
                conversation is not None
                and conversation["user_id"] is not None
                and conversation["user_id"] != user_id
            ):
                raise ConversationNotFoundError(session_id)

            created_at = (
                conversation["created_at"]
                if conversation is not None
                else saved_at
            )

            connection.execute(
                """
                INSERT INTO conversations (
                    session_id,
                    user_id,
                    created_at,
                    updated_at,
                    expires_at
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(session_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    updated_at = EXCLUDED.updated_at,
                    expires_at = EXCLUDED.expires_at
                """,
                (session_id, user_id, created_at, saved_at, expires_at),
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

            self._prune_oldest(connection, user_id)

        return self.get_conversation(user_id, session_id, now=saved_at)

    def get_conversation(
        self,
        user_id: str,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> SavedConversation:
        checked_at = now or self._now()

        with self._connect() as connection:
            self._cleanup_expired(connection, checked_at)

            conversation = connection.execute(
                """
                SELECT
                    session_id,
                    user_id,
                    created_at,
                    updated_at,
                    expires_at
                FROM conversations
                WHERE session_id = %s AND user_id = %s
                """,
                (session_id, user_id),
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

        return self._conversation_from_rows(conversation, messages)

    def list_conversations(
        self,
        user_id: str,
        *,
        now: datetime | None = None,
    ) -> SavedConversationList:
        checked_at = now or self._now()

        with self._connect() as connection:
            self._cleanup_expired(connection, checked_at)
            self._prune_oldest(connection, user_id)

            conversations = connection.execute(
                """
                SELECT
                    c.user_id,
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
                WHERE c.user_id = %s
                GROUP BY
                    c.user_id,
                    c.session_id,
                    c.created_at,
                    c.updated_at,
                    c.expires_at
                ORDER BY c.updated_at DESC, c.session_id DESC
                LIMIT %s
                """,
                (user_id, self.max_saved_chats),
            ).fetchall()

        return SavedConversationList(
            conversations=[
                SavedConversationSummary(
                    user_id=conversation["user_id"],
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

    def export_user_data(self, user_id: str) -> AccountExport:
        user = self.get_user(user_id)
        conversations: list[SavedConversation] = []

        with self._connect() as connection:
            self._cleanup_expired(connection, self._now())
            rows = connection.execute(
                """
                SELECT session_id
                FROM conversations
                WHERE user_id = %s
                ORDER BY updated_at DESC, session_id DESC
                """,
                (user_id,),
            ).fetchall()

        for row in rows:
            conversations.append(
                self.get_conversation(user_id, row["session_id"])
            )

        return AccountExport(
            user=user,
            conversations=conversations,
            exported_at=self._now(),
        )

    def delete_conversation(self, user_id: str, session_id: str) -> bool:
        with self._connect() as connection:
            result = connection.execute(
                """
                DELETE FROM conversations
                WHERE session_id = %s AND user_id = %s
                """,
                (session_id, user_id),
            )

        return result.rowcount > 0

    def delete_user_data(self, user_id: str) -> tuple[bool, int]:
        with self._connect() as connection:
            deleted_conversations = connection.execute(
                "DELETE FROM conversations WHERE user_id = %s",
                (user_id,),
            ).rowcount
            deleted_user = connection.execute(
                "DELETE FROM users WHERE user_id = %s",
                (user_id,),
            ).rowcount

        return deleted_user > 0, deleted_conversations

    def admin_summary(self) -> AdminSummary:
        now = self._now()

        with self._connect() as connection:
            self._cleanup_expired(connection, now)
            self._cleanup_reset_tokens(connection, now)
            row = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM users)::INTEGER AS users,
                    (
                        SELECT COUNT(*)
                        FROM conversations
                        WHERE user_id IS NOT NULL
                    )::INTEGER AS conversations,
                    (SELECT COUNT(*) FROM messages)::INTEGER AS messages,
                    (
                        SELECT COUNT(*)
                        FROM conversations
                        WHERE expires_at <= %s
                    )::INTEGER AS expiring_soon
                """,
                (now + timedelta(days=2),),
            ).fetchone()

        return AdminSummary(
            users=row["users"],
            conversations=row["conversations"],
            messages=row["messages"],
            expiring_soon=row["expiring_soon"],
            retention_days=self.retention_days,
            max_saved_chats=self.max_saved_chats,
            generated_at=now,
        )

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def _ensure_user_exists(
        self,
        connection: psycopg.Connection,
        user_id: str,
    ) -> None:
        user = connection.execute(
            "SELECT user_id FROM users WHERE user_id = %s",
            (user_id,),
        ).fetchone()
        if user is None:
            raise UserNotFoundError(user_id)

    def _cleanup_expired(
        self,
        connection: psycopg.Connection,
        now: datetime,
    ) -> None:
        connection.execute(
            "DELETE FROM conversations WHERE expires_at <= %s",
            (now,),
        )

    def _cleanup_reset_tokens(
        self,
        connection: psycopg.Connection,
        now: datetime,
    ) -> None:
        connection.execute(
            """
            DELETE FROM password_reset_tokens
            WHERE expires_at <= %s OR used_at IS NOT NULL
            """,
            (now,),
        )

    def _prune_oldest(
        self,
        connection: psycopg.Connection,
        user_id: str,
    ) -> None:
        connection.execute(
            """
            DELETE FROM conversations
            WHERE session_id IN (
                SELECT session_id
                FROM conversations
                WHERE user_id = %s
                ORDER BY updated_at DESC, session_id DESC
                OFFSET %s
            )
            """,
            (user_id, self.max_saved_chats),
        )

    def _conversation_from_rows(
        self,
        conversation: dict,
        messages: list[dict],
    ) -> SavedConversation:
        return SavedConversation(
            user_id=conversation["user_id"],
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

    @staticmethod
    def _hash_password(password: str) -> str:
        iterations = 260_000
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        ).hex()
        return f"pbkdf2_sha256${iterations}${salt}${digest}"

    @staticmethod
    def _hash_reset_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        try:
            algorithm, iterations, salt, expected = password_hash.split("$")
            if algorithm != "pbkdf2_sha256":
                return False
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                int(iterations),
            ).hex()
        except ValueError:
            return False

        return hmac.compare_digest(digest, expected)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)
