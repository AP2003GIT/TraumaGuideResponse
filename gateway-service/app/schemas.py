from typing import Literal

from pydantic import BaseModel, Field, field_validator


RiskLevel = Literal["standard", "elevated", "high", "immediate"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
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
    risk_level: RiskLevel
    mentions_self_harm: bool
    mentions_harm_to_others: bool
    needs_professional_support: bool
    brief_reason: str
    safe_reply: str | None


class ChatGenerationRequest(BaseModel):
    message: str
    history: list[ChatMessage]
    risk_level: Literal["standard", "elevated"]
    needs_professional_support: bool


class ChatGenerationResponse(BaseModel):
    reply: str
    model: str


class ChatResponse(BaseModel):
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


class SaveTurnRequest(BaseModel):
    user_message: str
    assistant_message: str
    risk_level: RiskLevel
    model: str | None
    request_id: str


class SavedMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    risk_level: RiskLevel | None = None
    model: str | None = None
    request_id: str
    created_at: str


class SavedConversation(BaseModel):
    session_id: str
    messages: list[SavedMessage]
    created_at: str
    updated_at: str
    expires_at: str
    retention_days: int


class SavedConversationSummary(BaseModel):
    session_id: str
    title: str
    last_message_preview: str
    message_count: int
    created_at: str
    updated_at: str
    expires_at: str
    retention_days: int


class SavedConversationList(BaseModel):
    conversations: list[SavedConversationSummary]
    max_saved_chats: int
    retention_days: int


class DeleteConversationResponse(BaseModel):
    deleted: bool


class DependencyStatus(BaseModel):
    gateway: str
    safety_service: str
    chat_service: str
    save_service: str
