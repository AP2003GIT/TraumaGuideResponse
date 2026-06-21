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


class SavedMessage(BaseModel):
    id: str
    role: Role
    content: str
    risk_level: RiskLevel | None = None
    model: str | None = None
    request_id: str
    created_at: datetime


class SavedConversation(BaseModel):
    session_id: str
    messages: list[SavedMessage]
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    retention_days: int


class DeleteConversationResponse(BaseModel):
    deleted: bool
