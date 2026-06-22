from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Path, Request, status
from fastapi.middleware.cors import CORSMiddleware

from app.auth import create_access_token, get_current_user
from app.clients import (
    DownstreamServiceError,
    delete_model,
    get_health,
    get_model,
    post_model,
)
from app.config import get_settings
from app.schemas import (
    AccountExport,
    AdminDashboard,
    AdminSummary,
    AuthRequest,
    AuthResponse,
    AuthenticatedUser,
    ChatGenerationRequest,
    ChatGenerationResponse,
    ChatRequest,
    ChatResponse,
    DeleteConversationResponse,
    DeleteUserDataResponse,
    DependencyStatus,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetRequestResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    RiskAssessment,
    SavedConversation,
    SavedConversationList,
    SaveTurnRequest,
)

settings = get_settings()


def _service_unavailable(
    exc: DownstreamServiceError,
    request_id: str,
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "request_id": request_id,
            "service": exc.service,
            "message": str(exc),
        },
    )


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
    save_status = await get_health(
        client=client,
        url=f"{settings.save_service_url}/health",
    )

    return DependencyStatus(
        gateway="healthy",
        safety_service=safety_status,
        chat_service=chat_status,
        save_service=save_status,
    )


@app.post(
    "/api/auth/register",
    response_model=AuthResponse,
    tags=["auth"],
)
async def register(
    payload: RegisterRequest,
    request: Request,
) -> AuthResponse:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    client: httpx.AsyncClient = request.app.state.http_client

    try:
        user = await post_model(
            client=client,
            service_name="save-service",
            url=f"{settings.save_service_url}/internal/auth/register",
            payload=payload,
            response_model=AuthenticatedUser,
            request_id=request_id,
        )
        assert isinstance(user, AuthenticatedUser)
    except DownstreamServiceError as exc:
        if exc.status_code == status.HTTP_409_CONFLICT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with that email already exists.",
            ) from exc
        raise _service_unavailable(exc, request_id)

    return AuthResponse(
        access_token=create_access_token(user, settings),
        user=user,
    )


@app.post(
    "/api/auth/login",
    response_model=AuthResponse,
    tags=["auth"],
)
async def login(
    payload: AuthRequest,
    request: Request,
) -> AuthResponse:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    client: httpx.AsyncClient = request.app.state.http_client

    try:
        user = await post_model(
            client=client,
            service_name="save-service",
            url=f"{settings.save_service_url}/internal/auth/login",
            payload=payload,
            response_model=AuthenticatedUser,
            request_id=request_id,
        )
        assert isinstance(user, AuthenticatedUser)
    except DownstreamServiceError as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            ) from exc
        raise _service_unavailable(exc, request_id)

    return AuthResponse(
        access_token=create_access_token(user, settings),
        user=user,
    )


@app.post(
    "/api/auth/password-reset/request",
    response_model=PasswordResetRequestResponse,
    tags=["auth"],
)
async def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
) -> PasswordResetRequestResponse:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    client: httpx.AsyncClient = request.app.state.http_client

    try:
        reset_request = await post_model(
            client=client,
            service_name="save-service",
            url=(
                f"{settings.save_service_url}/internal/auth/"
                "password-reset/request"
            ),
            payload=payload,
            response_model=PasswordResetRequestResponse,
            request_id=request_id,
        )
        assert isinstance(reset_request, PasswordResetRequestResponse)
        return reset_request
    except DownstreamServiceError as exc:
        raise _service_unavailable(exc, request_id)


@app.post(
    "/api/auth/password-reset/confirm",
    response_model=AuthResponse,
    tags=["auth"],
)
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    request: Request,
) -> AuthResponse:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    client: httpx.AsyncClient = request.app.state.http_client

    try:
        user = await post_model(
            client=client,
            service_name="save-service",
            url=(
                f"{settings.save_service_url}/internal/auth/"
                "password-reset/confirm"
            ),
            payload=payload,
            response_model=AuthenticatedUser,
            request_id=request_id,
        )
        assert isinstance(user, AuthenticatedUser)
    except DownstreamServiceError as exc:
        if exc.status_code == status.HTTP_400_BAD_REQUEST:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset code.",
            ) from exc
        raise _service_unavailable(exc, request_id)

    return AuthResponse(
        access_token=create_access_token(user, settings),
        user=user,
    )


@app.get(
    "/api/auth/me",
    response_model=AuthenticatedUser,
    tags=["auth"],
)
async def me(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    return user


@app.post(
    "/api/account/profile",
    response_model=AuthResponse,
    tags=["auth"],
)
async def update_account_profile(
    payload: ProfileUpdateRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthResponse:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    client: httpx.AsyncClient = request.app.state.http_client

    try:
        updated_user = await post_model(
            client=client,
            service_name="save-service",
            url=(
                f"{settings.save_service_url}/internal/users/"
                f"{user.user_id}/profile"
            ),
            payload=payload,
            response_model=AuthenticatedUser,
            request_id=request_id,
        )
        assert isinstance(updated_user, AuthenticatedUser)
    except DownstreamServiceError as exc:
        if exc.status_code == status.HTTP_409_CONFLICT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with that email already exists.",
            ) from exc
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect.",
            ) from exc
        raise _service_unavailable(exc, request_id)

    return AuthResponse(
        access_token=create_access_token(updated_user, settings),
        user=updated_user,
    )


@app.get(
    "/api/account/export",
    response_model=AccountExport,
    tags=["auth"],
)
async def export_account_data(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AccountExport:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    client: httpx.AsyncClient = request.app.state.http_client

    try:
        export = await get_model(
            client=client,
            service_name="save-service",
            url=(
                f"{settings.save_service_url}/internal/users/"
                f"{user.user_id}/export"
            ),
            response_model=AccountExport,
            request_id=request_id,
        )
        assert isinstance(export, AccountExport)
        return export
    except DownstreamServiceError as exc:
        raise _service_unavailable(exc, request_id)


@app.get(
    "/api/admin/dashboard",
    response_model=AdminDashboard,
    tags=["admin"],
)
async def admin_dashboard(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AdminDashboard:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    client: httpx.AsyncClient = request.app.state.http_client

    dependencies = await dependency_health(request)

    try:
        storage = await get_model(
            client=client,
            service_name="save-service",
            url=f"{settings.save_service_url}/internal/admin/summary",
            response_model=AdminSummary,
            request_id=request_id,
        )
        assert isinstance(storage, AdminSummary)
    except DownstreamServiceError as exc:
        raise _service_unavailable(exc, request_id)

    return AdminDashboard(
        dependencies=dependencies,
        storage=storage,
    )


@app.delete(
    "/api/account",
    response_model=DeleteUserDataResponse,
    tags=["auth"],
)
async def delete_account_data(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> DeleteUserDataResponse:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    client: httpx.AsyncClient = request.app.state.http_client

    try:
        deletion = await delete_model(
            client=client,
            service_name="save-service",
            url=f"{settings.save_service_url}/internal/users/{user.user_id}",
            response_model=DeleteUserDataResponse,
            request_id=request_id,
        )
        assert isinstance(deletion, DeleteUserDataResponse)
        return deletion
    except DownstreamServiceError as exc:
        raise _service_unavailable(exc, request_id)


async def save_exchange(
    *,
    client: httpx.AsyncClient,
    user_id: str,
    session_id: str | None,
    user_message: str,
    assistant_message: str,
    risk_level: str,
    model: str | None,
    request_id: str,
) -> bool:
    if not session_id:
        return False

    try:
        saved = await post_model(
            client=client,
            service_name="save-service",
            url=(
                f"{settings.save_service_url}/internal/users/{user_id}/"
                "conversations/"
                f"{session_id}/turns"
            ),
            payload=SaveTurnRequest(
                user_message=user_message,
                assistant_message=assistant_message,
                risk_level=risk_level,
                model=model,
                request_id=request_id,
            ),
            response_model=SavedConversation,
            request_id=request_id,
        )
        assert isinstance(saved, SavedConversation)
        return True
    except DownstreamServiceError:
        return False


@app.post(
    "/api/chat",
    response_model=ChatResponse,
    tags=["chat"],
)
async def chat(
    payload: ChatRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
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

            saved = await save_exchange(
                client=client,
                user_id=user.user_id,
                session_id=payload.session_id,
                user_message=payload.message,
                assistant_message=assessment.safe_reply,
                risk_level=assessment.risk_level,
                model=None,
                request_id=request_id,
            )

            return ChatResponse(
                reply=assessment.safe_reply,
                risk_level=assessment.risk_level,
                model=None,
                request_id=request_id,
                session_id=payload.session_id,
                saved=saved,
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

        saved = await save_exchange(
            client=client,
            user_id=user.user_id,
            session_id=payload.session_id,
            user_message=payload.message,
            assistant_message=generation.reply,
            risk_level=assessment.risk_level,
            model=generation.model,
            request_id=request_id,
        )

        return ChatResponse(
            reply=generation.reply,
            risk_level=assessment.risk_level,
            model=generation.model,
            request_id=request_id,
            session_id=payload.session_id,
            saved=saved,
        )

    except DownstreamServiceError as exc:
        # Safety failure is fail-closed: no normal generation is attempted.
        raise _service_unavailable(exc, request_id) from exc


@app.get(
    "/api/conversations",
    response_model=SavedConversationList,
    tags=["chat"],
)
async def list_saved_conversations(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> SavedConversationList:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    client: httpx.AsyncClient = request.app.state.http_client

    try:
        conversations = await get_model(
            client=client,
            service_name="save-service",
            url=(
                f"{settings.save_service_url}/internal/users/"
                f"{user.user_id}/conversations"
            ),
            response_model=SavedConversationList,
            request_id=request_id,
        )
        assert isinstance(conversations, SavedConversationList)
        return conversations
    except DownstreamServiceError as exc:
        raise _service_unavailable(exc, request_id) from exc


@app.get(
    "/api/conversations/{session_id}",
    response_model=SavedConversation,
    tags=["chat"],
)
async def get_saved_conversation(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    session_id: str = Path(min_length=1, max_length=120),
) -> SavedConversation:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    client: httpx.AsyncClient = request.app.state.http_client

    try:
        conversation = await get_model(
            client=client,
            service_name="save-service",
            url=(
                f"{settings.save_service_url}/internal/users/"
                f"{user.user_id}/conversations/{session_id}"
            ),
            response_model=SavedConversation,
            request_id=request_id,
        )
        assert isinstance(conversation, SavedConversation)
        return conversation
    except DownstreamServiceError as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved conversation not found.",
            ) from exc

        raise _service_unavailable(exc, request_id) from exc


@app.delete(
    "/api/conversations/{session_id}",
    response_model=DeleteConversationResponse,
    tags=["chat"],
)
async def delete_saved_conversation(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    session_id: str = Path(min_length=1, max_length=120),
) -> DeleteConversationResponse:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    client: httpx.AsyncClient = request.app.state.http_client

    try:
        deletion = await delete_model(
            client=client,
            service_name="save-service",
            url=(
                f"{settings.save_service_url}/internal/users/"
                f"{user.user_id}/conversations/{session_id}"
            ),
            response_model=DeleteConversationResponse,
            request_id=request_id,
        )
        assert isinstance(deletion, DeleteConversationResponse)
        return deletion
    except DownstreamServiceError as exc:
        raise _service_unavailable(exc, request_id) from exc
