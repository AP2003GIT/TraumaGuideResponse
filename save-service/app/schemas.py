from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


RiskLevel = Literal["standard", "elevated", "high", "immediate"]
Role = Literal["user", "assistant"]


class SaveTurnRequest(BaseModel):
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
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def display_name_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Display name cannot be blank.")
        return cleaned


class AuthenticatedUser(BaseModel):
    user_id: str
    email: str
    display_name: str


class SavedMessage(BaseModel):
    id: str
    role: Role
    content: str
    risk_level: RiskLevel | None = None
    model: str | None = None
    request_id: str
    created_at: datetime


class SavedConversation(BaseModel):
    user_id: str
    session_id: str
    messages: list[SavedMessage]
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    retention_days: int


class SavedConversationSummary(BaseModel):
    user_id: str
    session_id: str
    title: str
    last_message_preview: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    retention_days: int


class SavedConversationList(BaseModel):
    conversations: list[SavedConversationSummary]
    max_saved_chats: int
    retention_days: int


class DeleteConversationResponse(BaseModel):
    deleted: bool


class DeleteUserDataResponse(BaseModel):
    deleted: bool
    deleted_conversations: int


class AccountExport(BaseModel):
    user: AuthenticatedUser
    conversations: list[SavedConversation]
    exported_at: datetime
