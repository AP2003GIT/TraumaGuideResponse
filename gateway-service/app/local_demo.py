from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas import (
    AccountExport,
    AdminSummary,
    AuthRequest,
    AuthenticatedUser,
    ChatGenerationRequest,
    ChatGenerationResponse,
    ChatRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetRequestResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    RiskAssessment,
    SaveTurnRequest,
    SavedConversation,
    SavedConversationList,
    SavedConversationSummary,
    SavedMessage,
)


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


class LocalDemoStore:
    def __init__(
        self,
        *,
        retention_days: int,
        max_saved_chats: int,
        admin_emails: list[str],
    ) -> None:
        self.retention_days = retention_days
        self.max_saved_chats = max_saved_chats
        self.admin_emails = {
            email.strip().lower() for email in admin_emails if email.strip()
        }
        self.users_by_email: dict[str, dict[str, str]] = {}
        self.users_by_id: dict[str, dict[str, str]] = {}
        self.reset_tokens: dict[str, dict[str, str | datetime]] = {}
        self.conversations: dict[str, SavedConversation] = {}

    def create_user(self, payload: RegisterRequest) -> AuthenticatedUser:
        email = payload.email.strip().lower()
        if email in self.users_by_email:
            raise AccountAlreadyExistsError(email)

        user = {
            "user_id": str(uuid4()),
            "email": email,
            "display_name": payload.display_name.strip(),
            "role": self._role_for_email(email),
            "password_hash": self._hash_password(payload.password),
        }
        self.users_by_email[email] = user
        self.users_by_id[user["user_id"]] = user
        return self._user_from_record(user)

    def authenticate_user(self, payload: AuthRequest) -> AuthenticatedUser:
        email = payload.email.strip().lower()
        user = self.users_by_email.get(email)
        if user is None or not self._verify_password(
            payload.password,
            user["password_hash"],
        ):
            raise InvalidCredentialsError("Invalid email or password.")
        return self._user_from_record(user)

    def get_user(self, user_id: str) -> AuthenticatedUser:
        user = self.users_by_id.get(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return self._user_from_record(user)

    def update_user_profile(
        self,
        user_id: str,
        payload: ProfileUpdateRequest,
    ) -> AuthenticatedUser:
        user = self.users_by_id.get(user_id)
        if user is None:
            raise UserNotFoundError(user_id)

        email = payload.email.strip().lower()
        existing = self.users_by_email.get(email)
        if existing is not None and existing["user_id"] != user_id:
            raise AccountAlreadyExistsError(email)

        if payload.new_password:
            if not payload.current_password or not self._verify_password(
                payload.current_password,
                user["password_hash"],
            ):
                raise InvalidCredentialsError("Current password is incorrect.")
            user["password_hash"] = self._hash_password(payload.new_password)

        if email != user["email"]:
            self.users_by_email.pop(user["email"], None)
            self.users_by_email[email] = user

        user["email"] = email
        user["display_name"] = payload.display_name.strip()
        user["role"] = self._role_for_email(email, user["role"])
        return self._user_from_record(user)

    def request_password_reset(
        self,
        payload: PasswordResetRequest,
    ) -> PasswordResetRequestResponse:
        user = self.users_by_email.get(payload.email.strip().lower())
        if user is None:
            return PasswordResetRequestResponse(
                accepted=True,
                dev_reset_token=None,
            )

        token = secrets.token_urlsafe(32)
        self.reset_tokens[token] = {
            "user_id": user["user_id"],
            "expires_at": self._now() + timedelta(minutes=30),
        }
        return PasswordResetRequestResponse(
            accepted=True,
            dev_reset_token=token,
        )

    def confirm_password_reset(
        self,
        payload: PasswordResetConfirmRequest,
    ) -> AuthenticatedUser:
        reset = self.reset_tokens.get(payload.reset_token)
        if (
            reset is None
            or not isinstance(reset["expires_at"], datetime)
            or reset["expires_at"] <= self._now()
        ):
            raise InvalidResetTokenError("Invalid or expired reset code.")

        user = self.users_by_id.get(str(reset["user_id"]))
        if user is None:
            raise InvalidResetTokenError("Invalid or expired reset code.")

        user["password_hash"] = self._hash_password(payload.new_password)
        self.reset_tokens.pop(payload.reset_token, None)
        return self._user_from_record(user)

    def save_turn(
        self,
        user_id: str,
        session_id: str,
        payload: SaveTurnRequest,
    ) -> SavedConversation:
        self.get_user(user_id)
        now = self._iso_now()
        key = self._conversation_key(user_id, session_id)
        conversation = self.conversations.get(key)
        if conversation is None:
            conversation = SavedConversation(
                user_id=user_id,
                session_id=session_id,
                messages=[],
                created_at=now,
                updated_at=now,
                expires_at=self._expires_at(),
                retention_days=self.retention_days,
            )

        conversation.messages.extend(
            [
                SavedMessage(
                    id=str(uuid4()),
                    role="user",
                    content=payload.user_message,
                    risk_level=None,
                    model=None,
                    request_id=payload.request_id,
                    created_at=now,
                ),
                SavedMessage(
                    id=str(uuid4()),
                    role="assistant",
                    content=payload.assistant_message,
                    risk_level=payload.risk_level,
                    model=payload.model,
                    request_id=payload.request_id,
                    created_at=now,
                ),
            ]
        )
        conversation.updated_at = now
        conversation.expires_at = self._expires_at()
        self.conversations[key] = conversation
        self._prune_oldest(user_id)
        return conversation

    def list_conversations(self, user_id: str) -> SavedConversationList:
        self.get_user(user_id)
        conversations = sorted(
            [
                conversation
                for key, conversation in self.conversations.items()
                if key.startswith(f"{user_id}:")
            ],
            key=lambda item: item.updated_at,
            reverse=True,
        )[: self.max_saved_chats]

        return SavedConversationList(
            conversations=[
                SavedConversationSummary(
                    user_id=conversation.user_id,
                    session_id=conversation.session_id,
                    title=self._title_for(conversation),
                    last_message_preview=self._preview_for(conversation),
                    message_count=len(conversation.messages),
                    created_at=conversation.created_at,
                    updated_at=conversation.updated_at,
                    expires_at=conversation.expires_at,
                    retention_days=self.retention_days,
                )
                for conversation in conversations
            ],
            max_saved_chats=self.max_saved_chats,
            retention_days=self.retention_days,
        )

    def get_conversation(
        self,
        user_id: str,
        session_id: str,
    ) -> SavedConversation:
        conversation = self.conversations.get(
            self._conversation_key(user_id, session_id)
        )
        if conversation is None:
            raise ConversationNotFoundError(session_id)
        return conversation

    def delete_conversation(self, user_id: str, session_id: str) -> bool:
        return (
            self.conversations.pop(
                self._conversation_key(user_id, session_id),
                None,
            )
            is not None
        )

    def export_user_data(self, user_id: str) -> AccountExport:
        return AccountExport(
            user=self.get_user(user_id),
            conversations=[
                conversation
                for key, conversation in self.conversations.items()
                if key.startswith(f"{user_id}:")
            ],
            exported_at=self._iso_now(),
        )

    def delete_user_data(self, user_id: str) -> tuple[bool, int]:
        deleted_user = self.users_by_id.pop(user_id, None)
        if deleted_user is not None:
            self.users_by_email.pop(deleted_user["email"], None)

        conversation_keys = [
            key for key in self.conversations if key.startswith(f"{user_id}:")
        ]
        for key in conversation_keys:
            self.conversations.pop(key, None)

        return deleted_user is not None, len(conversation_keys)

    def admin_summary(self) -> AdminSummary:
        return AdminSummary(
            users=len(self.users_by_id),
            conversations=len(self.conversations),
            messages=sum(
                len(conversation.messages)
                for conversation in self.conversations.values()
            ),
            expiring_soon=0,
            retention_days=self.retention_days,
            max_saved_chats=self.max_saved_chats,
            generated_at=self._iso_now(),
        )

    def assess_risk(self, payload: ChatRequest) -> RiskAssessment:
        message = payload.message.lower()
        immediate_terms = [
            "kill myself",
            "end my life",
            "suicide",
            "hurt myself",
            "harm myself",
        ]
        if any(term in message for term in immediate_terms):
            return RiskAssessment(
                risk_level="immediate",
                mentions_self_harm=True,
                mentions_harm_to_others=False,
                needs_professional_support=True,
                brief_reason="The message may mention immediate self-harm.",
                safe_reply=(
                    "I'm really sorry you're feeling this much pain. "
                    "If you might hurt yourself or feel unable to stay safe, "
                    "call emergency services now. In the U.S. or Canada, call "
                    "or text 988 for immediate crisis support. If you can, "
                    "move away from anything you could use to hurt yourself "
                    "and contact someone you trust right now."
                ),
            )

        elevated_terms = ["panic", "overwhelmed", "hopeless", "can't cope"]
        elevated = any(term in message for term in elevated_terms)
        return RiskAssessment(
            risk_level="elevated" if elevated else "standard",
            mentions_self_harm=False,
            mentions_harm_to_others=False,
            needs_professional_support=elevated,
            brief_reason="Single-service demo fallback assessment.",
            safe_reply=None,
        )

    def generate_reply(
        self,
        payload: ChatGenerationRequest,
    ) -> ChatGenerationResponse:
        if payload.needs_professional_support:
            reply = (
                "That sounds like a lot to carry. Try one small step first: "
                "put both feet on the floor, breathe in for four counts, out "
                "for six, and name five things you can see. If this has been "
                "going on for a while or feels unmanageable, reaching out to "
                "a trusted person or a mental-health professional could help."
            )
        else:
            reply = (
                "I hear you. A useful next step is to slow the moment down: "
                "name what you are feeling, what triggered it, and one small "
                "thing you can do in the next ten minutes. You do not have to "
                "solve everything at once."
            )

        return ChatGenerationResponse(
            reply=reply,
            model="single-service-demo",
        )

    def _role_for_email(self, email: str, stored_role: str = "user") -> str:
        if email.strip().lower() in self.admin_emails:
            return "admin"
        if stored_role == "admin":
            return "admin"
        return "user"

    def _user_from_record(self, user: dict[str, str]) -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id=user["user_id"],
            email=user["email"],
            display_name=user["display_name"],
            role=self._role_for_email(user["email"], user["role"]),
        )

    def _conversation_key(self, user_id: str, session_id: str) -> str:
        return f"{user_id}:{session_id}"

    def _prune_oldest(self, user_id: str) -> None:
        conversations = sorted(
            [
                conversation
                for key, conversation in self.conversations.items()
                if key.startswith(f"{user_id}:")
            ],
            key=lambda item: item.updated_at,
            reverse=True,
        )
        for conversation in conversations[self.max_saved_chats :]:
            self.conversations.pop(
                self._conversation_key(user_id, conversation.session_id),
                None,
            )

    def _title_for(self, conversation: SavedConversation) -> str:
        for message in conversation.messages:
            if message.role == "user":
                return message.content[:120] or "Untitled chat"
        return "Untitled chat"

    def _preview_for(self, conversation: SavedConversation) -> str:
        if not conversation.messages:
            return ""
        return conversation.messages[-1].content[:180]

    def _expires_at(self) -> str:
        return (
            self._now() + timedelta(days=self.retention_days)
        ).isoformat()

    def _iso_now(self) -> str:
        return self._now().isoformat()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

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
