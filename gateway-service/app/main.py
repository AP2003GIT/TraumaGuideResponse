from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from app.clients import DownstreamServiceError, get_health, post_model
from app.config import get_settings
from app.schemas import (
    ChatGenerationRequest,
    ChatGenerationResponse,
    ChatRequest,
    ChatResponse,
    DependencyStatus,
    RiskAssessment,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.request_timeout_seconds)
    )
    yield
    await app.state.http_client.aclose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Public API gateway that routes every message through the "
        "safety service before the chat service."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {
        "service": "gateway-service",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get(
    "/health/dependencies",
    response_model=DependencyStatus,
    tags=["system"],
)
async def dependency_health(request: Request) -> DependencyStatus:
    client: httpx.AsyncClient = request.app.state.http_client

    safety_status = await get_health(
        client=client,
        url=f"{settings.safety_service_url}/health",
    )
    chat_status = await get_health(
        client=client,
        url=f"{settings.chat_service_url}/health",
    )

    return DependencyStatus(
        gateway="healthy",
        safety_service=safety_status,
        chat_service=chat_status,
    )


@app.post(
    "/api/chat",
    response_model=ChatResponse,
    tags=["chat"],
)
async def chat(
    payload: ChatRequest,
    request: Request,
) -> ChatResponse:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    client: httpx.AsyncClient = request.app.state.http_client

    try:
        assessment = await post_model(
            client=client,
            service_name="safety-service",
            url=f"{settings.safety_service_url}/internal/classify",
            payload=payload,
            response_model=RiskAssessment,
            request_id=request_id,
        )
        assert isinstance(assessment, RiskAssessment)

        if assessment.risk_level in {"high", "immediate"}:
            if not assessment.safe_reply:
                raise DownstreamServiceError(
                    "safety-service",
                    "Safety response was missing for a high-risk message.",
                )

            return ChatResponse(
                reply=assessment.safe_reply,
                risk_level=assessment.risk_level,
                model=None,
                request_id=request_id,
            )

        generation_request = ChatGenerationRequest(
            message=payload.message,
            history=payload.history,
            risk_level=assessment.risk_level,
            needs_professional_support=(
                assessment.needs_professional_support
            ),
        )

        generation = await post_model(
            client=client,
            service_name="chat-service",
            url=f"{settings.chat_service_url}/internal/generate",
            payload=generation_request,
            response_model=ChatGenerationResponse,
            request_id=request_id,
        )
        assert isinstance(generation, ChatGenerationResponse)

        return ChatResponse(
            reply=generation.reply,
            risk_level=assessment.risk_level,
            model=generation.model,
            request_id=request_id,
        )

    except DownstreamServiceError as exc:
        # Safety failure is fail-closed: no normal generation is attempted.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "request_id": request_id,
                "service": exc.service,
                "message": str(exc),
            },
        ) from exc
