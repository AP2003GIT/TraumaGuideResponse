from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


RiskLevel = Literal["standard", "elevated", "high", "immediate"]
Role = Literal["user", "assistant"]
UserRole = Literal["user", "admin"]


class SaveTurnRequest(BaseModel):
    """Request payload for storing one user/assistant exchange."""
    user_message: str = Field(min_length=1, max_length=4000)
    assistant_message: str = Field(min_length=1, max_length=4000)
    risk_level: RiskLevel
    model: str | None = Field(default=None, max_length=200)
    request_id: str = Field(min_length=1, max_length=120)

    @field_validator("user_message", "assistant_message", "request_id")
    @classmethod
    def value_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value cannot be blank.")
        return cleaned


class AuthRequest(BaseModel):
    """Login request containing normalized email and password."""
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def email_must_be_normalized(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned:
            raise ValueError("Enter a valid email address.")
        return cleaned


class RegisterRequest(AuthRequest):
    """Registration request for creating a local account."""
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def display_name_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Display name cannot be blank.")
        return cleaned


class AuthenticatedUser(BaseModel):
    """Authenticated user identity embedded in API responses and tokens."""
    user_id: str
    email: str
    display_name: str
    role: UserRole = "user"


class ProfileUpdateRequest(BaseModel):
    """Request payload for updating account profile fields."""
    display_name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=254)
    current_password: str | None = Field(default=None, max_length=128)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("display_name")
    @classmethod
    def display_name_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Display name cannot be blank.")
        return cleaned

    @field_validator("email")
    @classmethod
    def email_must_be_normalized(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned:
            raise ValueError("Enter a valid email address.")
        return cleaned


class PasswordResetRequest(BaseModel):
    """Request payload for starting a password reset flow."""
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def email_must_be_normalized(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned:
            raise ValueError("Enter a valid email address.")
        return cleaned


class PasswordResetRequestResponse(BaseModel):
    """Response payload for password reset requests."""
    accepted: bool
    dev_reset_token: str | None = None


class PasswordResetConfirmRequest(BaseModel):
    """Request payload for completing a password reset."""
    reset_token: str = Field(min_length=16, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("reset_token")
    @classmethod
    def token_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Reset token cannot be blank.")
        return cleaned


class SavedMessage(BaseModel):
    """Persisted message record in a saved conversation."""
    id: str
    role: Role
    content: str
    risk_level: RiskLevel | None = None
    model: str | None = None
    request_id: str
    created_at: datetime


class SavedConversation(BaseModel):
    """Full saved conversation with messages and metadata."""
    user_id: str
    session_id: str
    messages: list[SavedMessage]
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    retention_days: int
    title: str | None = None
    pinned: bool = False
    archived: bool = False


class SavedConversationSummary(BaseModel):
    """List-view summary of a saved conversation."""
    user_id: str
    session_id: str
    title: str
    last_message_preview: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    retention_days: int
    pinned: bool = False
    archived: bool = False


class ConversationMetadataUpdate(BaseModel):
    """Partial metadata update for a saved conversation."""
    title: str | None = Field(default=None, max_length=120)
    pinned: bool | None = None
    archived: bool | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value

        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Title cannot be blank.")
        return cleaned


class SavedConversationList(BaseModel):
    """Paginated-style response for retained saved conversations."""
    conversations: list[SavedConversationSummary]
    max_saved_chats: int
    retention_days: int


class DeleteConversationResponse(BaseModel):
    """Response returned after deleting a conversation."""
    deleted: bool


class DeleteUserDataResponse(BaseModel):
    """Response returned after deleting an account and its conversations."""
    deleted: bool
    deleted_conversations: int


class AccountExport(BaseModel):
    """Export payload containing user data and saved conversations."""
    user: AuthenticatedUser
    conversations: list[SavedConversation]
    exported_at: datetime


class AdminSummary(BaseModel):
    """Storage metrics shown in the admin dashboard."""
    users: int
    conversations: int
    messages: int
    expiring_soon: int
    retention_days: int
    max_saved_chats: int
    generated_at: datetime
