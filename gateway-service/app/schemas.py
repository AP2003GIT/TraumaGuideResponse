from typing import Literal

from pydantic import BaseModel, Field, field_validator


RiskLevel = Literal["standard", "elevated", "high", "immediate"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message cannot be blank.")
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
    disclaimer: str = (
        "General emotional support and psychoeducation only; "
        "not diagnosis, treatment, or emergency care."
    )


class DependencyStatus(BaseModel):
    gateway: str
    safety_service: str
    chat_service: str
