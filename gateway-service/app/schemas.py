from typing import Literal

from pydantic import BaseModel, Field, field_validator


RiskLevel = Literal["standard", "elevated", "high", "immediate"]
UserRole = Literal["user", "admin"]
ServiceMode = Literal["live", "fallback", "offline"]


class ChatMessage(BaseModel):
    """Single chat message exchanged between services."""
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    """Gateway request payload for a chat turn."""
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    session_id: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message cannot be blank.")
        return cleaned

    @field_validator("session_id")
    @classmethod
    def session_id_must_not_be_blank(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return value

        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Session ID cannot be blank.")
        return cleaned


class RiskAssessment(BaseModel):
    """Normalized safety assessment used by the platform."""
    risk_level: RiskLevel
    mentions_self_harm: bool
    mentions_harm_to_others: bool
    needs_professional_support: bool
    brief_reason: str
    safe_reply: str | None


class ChatGenerationRequest(BaseModel):
    """Chat-service request payload for response generation."""
    message: str
    history: list[ChatMessage]
    risk_level: Literal["standard", "elevated"]
    needs_professional_support: bool


class ChatGenerationResponse(BaseModel):
    """Chat-service response containing generated text and model metadata."""
    reply: str
    model: str


class ChatResponse(BaseModel):
    """Gateway response returned to the frontend after a chat turn."""
    reply: str
    risk_level: RiskLevel
    model: str | None
    request_id: str
    session_id: str | None = None
    saved: bool = False
    disclaimer: str = (
        "General emotional support and psychoeducation only; "
        "not diagnosis, treatment, or emergency care."
    )


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


class AuthResponse(BaseModel):
    """Bearer token response returned after authentication."""
    access_token: str
    token_type: str = "bearer"
    user: AuthenticatedUser


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


class SaveTurnRequest(BaseModel):
    """Request payload for storing one user/assistant exchange."""
    user_message: str
    assistant_message: str
    risk_level: RiskLevel
    model: str | None
    request_id: str


class SavedMessage(BaseModel):
    """Persisted message record in a saved conversation."""
    id: str
    role: Literal["user", "assistant"]
    content: str
    risk_level: RiskLevel | None = None
    model: str | None = None
    request_id: str
    created_at: str


class SavedConversation(BaseModel):
    """Full saved conversation with messages and metadata."""
    user_id: str
    session_id: str
    messages: list[SavedMessage]
    created_at: str
    updated_at: str
    expires_at: str
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
    created_at: str
    updated_at: str
    expires_at: str
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
    exported_at: str


class AdminSummary(BaseModel):
    """Storage metrics shown in the admin dashboard."""
    users: int
    conversations: int
    messages: int
    expiring_soon: int
    retention_days: int
    max_saved_chats: int
    generated_at: str


class DependencyStatus(BaseModel):
    """Gateway dependency health and fallback-mode status."""
    gateway: str
    safety_service: str
    chat_service: str
    save_service: str
    mode: ServiceMode = "live"
    fallback_enabled: bool = False
    checked_at: str | None = None
    details: dict[str, str | None] = Field(default_factory=dict)


class AdminDashboard(BaseModel):
    """Admin dashboard payload combining dependency and storage health."""
    dependencies: DependencyStatus
    storage: AdminSummary
