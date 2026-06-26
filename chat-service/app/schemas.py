from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatMessage(BaseModel):
    """Single chat message exchanged between services."""
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatGenerationRequest(BaseModel):
    """Chat-service request payload for response generation."""
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    risk_level: Literal["standard", "elevated"]
    needs_professional_support: bool

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message cannot be blank.")
        return cleaned


class ChatGenerationResponse(BaseModel):
    """Chat-service response containing generated text and model metadata."""
    reply: str
    model: str
