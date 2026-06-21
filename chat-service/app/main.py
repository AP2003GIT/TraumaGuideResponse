from functools import lru_cache

from fastapi import FastAPI, HTTPException, status

from app.config import get_settings
from app.gemini_service import GeminiChatService
from app.schemas import (
    ChatGenerationRequest,
    ChatGenerationResponse,
)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Internal service for normal and elevated-risk supportive "
        "response generation."
    ),
)


@lru_cache
def get_chat_service() -> GeminiChatService:
    return GeminiChatService(settings)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {
        "service": "chat-service",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post(
    "/internal/generate",
    response_model=ChatGenerationResponse,
    tags=["internal"],
)
async def generate(
    payload: ChatGenerationRequest,
) -> ChatGenerationResponse:
    try:
        return await get_chat_service().generate(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat generation failed.",
        ) from exc
