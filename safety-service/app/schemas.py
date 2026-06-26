from typing import Literal

from pydantic import BaseModel, Field, field_validator


RiskLevel = Literal["standard", "elevated", "high", "immediate"]


class ChatMessage(BaseModel):
    """Single chat message exchanged between services."""
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class RiskRequest(BaseModel):
    """Safety-service request payload for risk classification."""
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message cannot be blank.")
        return cleaned


class ModelRiskAssessment(BaseModel):
    """Structured risk assessment returned by the model."""
    risk_level: RiskLevel
    mentions_self_harm: bool
    mentions_harm_to_others: bool
    needs_professional_support: bool
    brief_reason: str = Field(min_length=1, max_length=300)


class RiskAssessment(ModelRiskAssessment):
    """Normalized safety assessment used by the platform."""
    safe_reply: str | None
