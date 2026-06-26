from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os
from pathlib import Path as FilePath
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Path, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.auth import create_access_token, get_current_user, require_admin_user
from app.clients import (
    DownstreamServiceError,
    delete_model,
    get_health_detail,
    get_model,
    patch_model,
    post_model,
)
from app.config import get_settings
from app.local_demo import (
    AccountAlreadyExistsError,
    ConversationNotFoundError,
    InvalidCredentialsError,
    InvalidResetTokenError,
    LocalDemoStore,
    UserNotFoundError,
)
from app.rate_limit import check_rate_limit
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
    ConversationMetadataUpdate,
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
logger = logging.getLogger("gateway-service")

# When the frontend is built into frontend/dist, the gateway can serve the
# React app and API from the same Render service.
FRONTEND_DIST = FilePath(__file__).resolve().parents[2] / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"


# Converts downstream microservice failures into one consistent API shape for
# the frontend. The request_id helps connect UI errors with service logs.
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


# Logs configuration that is easy to miss during local/Render deploys.
def _log_startup_config() -> None:
    warnings: list[str] = []
    if settings.auth_token_secret == "replace-this-development-auth-secret":
        warnings.append("AUTH_TOKEN_SECRET is using the development default.")
    if settings.single_service_fallback:
        warnings.append(
            "Single-service fallback is enabled. "
            f"Fallback data path: {settings.fallback_data_path}"
        )
    if not os.getenv("GEMINI_API_KEY"):
        warnings.append(
            "GEMINI_API_KEY is not set in the gateway environment. "
            "Safety/chat services may still have their own env, but local "
            "classification can fail if they share this config."
        )

    for warning in warnings:
        logger.warning("startup_config_warning: %s", warning)


# Structured warning used any time the gateway falls back or returns a
# downstream error. This keeps service failure debugging searchable.
def _log_downstream_failure(
    *,
    route: str,
    request_id: str,
    exc: DownstreamServiceError,
    fallback_used: bool,
) -> None:
    logger.warning(
        "downstream_failure route=%s request_id=%s service=%s "
        "status_code=%s fallback_used=%s error=%s",
        route,
        request_id,
        exc.service,
        exc.status_code,
        fallback_used,
        str(exc),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One shared HTTP client avoids reconnecting to downstream services on
    # every request. The demo store backs single-service fallback mode.
    _log_startup_config()
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.request_timeout_seconds)
    )
    app.state.demo_store = LocalDemoStore(
        retention_days=settings.chat_retention_days,
        max_saved_chats=settings.chat_max_saved_chats,
        admin_emails=settings.admin_emails,
        storage_path=settings.fallback_data_path,
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

# Static assets are mounted separately so hashed Vite files load quickly while
# API routes continue to live under /api and /health.
if FRONTEND_ASSETS.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_ASSETS),
        name="frontend-assets",
    )


def demo_store(request: Request) -> LocalDemoStore:
    return request.app.state.demo_store


def fallback_enabled() -> bool:
    return settings.single_service_fallback


@app.get("/", tags=["system"])
async def root():
    # Render should show the frontend on the root URL when dist exists. During
    # backend-only development, return a small service status payload instead.
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)

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

    # This endpoint powers both the header service chip and admin diagnostics.
    safety_status, safety_detail = await get_health_detail(
        client=client,
        url=f"{settings.safety_service_url}/health",
    )
    chat_status, chat_detail = await get_health_detail(
        client=client,
        url=f"{settings.chat_service_url}/health",
    )
    save_status, save_detail = await get_health_detail(
        client=client,
        url=f"{settings.save_service_url}/health",
    )
    downstream_statuses = [safety_status, chat_status, save_status]
    mode = (
        "live"
        if all(service == "healthy" for service in downstream_statuses)
        else "fallback"
        if fallback_enabled()
        else "offline"
    )

    return DependencyStatus(
        gateway="healthy",
        safety_service=safety_status,
        chat_service=chat_status,
        save_service=save_status,
        mode=mode,
        fallback_enabled=fallback_enabled(),
        checked_at=datetime.now(timezone.utc).isoformat(),
        details={
            "safety_service": safety_detail,
            "chat_service": chat_detail,
            "save_service": save_detail,
        },
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
    # Auth is owned by save-service in normal mode and mirrored by LocalDemoStore
    # when running as a single service.
    check_rate_limit(
        request,
        bucket="auth",
        max_requests=settings.auth_rate_limit_per_minute,
        window_seconds=60,
    )
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
        if fallback_enabled():
            try:
                user = demo_store(request).create_user(payload)
            except AccountAlreadyExistsError as fallback_exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An account with that email already exists.",
                ) from fallback_exc
        else:
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
    check_rate_limit(
        request,
        bucket="auth",
        max_requests=settings.auth_rate_limit_per_minute,
        window_seconds=60,
    )
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
        if fallback_enabled():
            try:
                user = demo_store(request).authenticate_user(payload)
            except InvalidCredentialsError as fallback_exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password.",
                ) from fallback_exc
        else:
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
    check_rate_limit(
        request,
        bucket="auth",
        max_requests=settings.auth_rate_limit_per_minute,
        window_seconds=60,
    )
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
        if fallback_enabled():
            return demo_store(request).request_password_reset(payload)
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
    check_rate_limit(
        request,
        bucket="auth",
        max_requests=settings.auth_rate_limit_per_minute,
        window_seconds=60,
    )
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
        if fallback_enabled():
            try:
                user = demo_store(request).confirm_password_reset(payload)
            except InvalidResetTokenError as fallback_exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired reset code.",
                ) from fallback_exc
        else:
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
        if fallback_enabled():
            try:
                updated_user = demo_store(request).update_user_profile(
                    user.user_id,
                    payload,
                )
            except AccountAlreadyExistsError as fallback_exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An account with that email already exists.",
                ) from fallback_exc
            except InvalidCredentialsError as fallback_exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Current password is incorrect.",
                ) from fallback_exc
            except UserNotFoundError as fallback_exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found.",
                ) from fallback_exc
        else:
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
        if fallback_enabled():
            try:
                return demo_store(request).export_user_data(user.user_id)
            except UserNotFoundError as fallback_exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found.",
                ) from fallback_exc
        raise _service_unavailable(exc, request_id)


@app.get(
    "/api/admin/dashboard",
    response_model=AdminDashboard,
    tags=["admin"],
)
async def admin_dashboard(
    request: Request,
    user: AuthenticatedUser = Depends(require_admin_user),
) -> AdminDashboard:
    # Admin combines live dependency status with storage metrics. The frontend
    # hides this tab unless the authenticated user role is admin.
    check_rate_limit(
        request,
        bucket="admin",
        max_requests=settings.admin_rate_limit_per_minute,
        window_seconds=60,
    )
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
        if fallback_enabled():
            storage = demo_store(request).admin_summary()
        else:
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
        if fallback_enabled():
            deleted, deleted_conversations = demo_store(
                request
            ).delete_user_data(user.user_id)
            return DeleteUserDataResponse(
                deleted=deleted,
                deleted_conversations=deleted_conversations,
            )
        raise _service_unavailable(exc, request_id)


async def save_exchange(
    *,
    client: httpx.AsyncClient,
    request: Request,
    user_id: str,
    session_id: str | None,
    user_message: str,
    assistant_message: str,
    risk_level: str,
    model: str | None,
    request_id: str,
) -> bool:
    # Chat saving is best-effort: the user can still receive a reply if the save
    # service is down, but the response tells the frontend whether saving worked.
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
    except DownstreamServiceError as exc:
        _log_downstream_failure(
            route="save_exchange",
            request_id=request_id,
            exc=exc,
            fallback_used=fallback_enabled(),
        )
        if fallback_enabled():
            try:
                demo_store(request).save_turn(
                    user_id,
                    session_id,
                    SaveTurnRequest(
                        user_message=user_message,
                        assistant_message=assistant_message,
                        risk_level=risk_level,
                        model=model,
                        request_id=request_id,
                    ),
                )
                return True
            except (ConversationNotFoundError, UserNotFoundError):
                return False
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
    # Main orchestration path: safety classification first, then generation,
    # then save the user/assistant turn.
    check_rate_limit(
        request,
        bucket="chat",
        max_requests=settings.chat_rate_limit_per_minute,
        window_seconds=60,
    )
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
            # High-risk content gets the safety service response directly; no
            # general model generation is attempted.
            if not assessment.safe_reply:
                raise DownstreamServiceError(
                    "safety-service",
                    "Safety response was missing for a high-risk message.",
                )

            saved = await save_exchange(
                client=client,
                request=request,
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
            request=request,
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
        _log_downstream_failure(
            route="chat",
            request_id=request_id,
            exc=exc,
            fallback_used=fallback_enabled(),
        )
        if not fallback_enabled():
            # Safety failure is fail-closed: no normal generation is attempted.
            raise _service_unavailable(exc, request_id) from exc

        # Single-service fallback keeps the demo usable without paid/remote
        # dependencies while preserving the same response shape.
        assessment = demo_store(request).assess_risk(payload)
        if assessment.risk_level in {"high", "immediate"}:
            reply = assessment.safe_reply or (
                "If you may be in immediate danger, contact emergency "
                "services now or call/text 988 in the U.S. or Canada."
            )
            model = None
        else:
            generation = demo_store(request).generate_reply(
                ChatGenerationRequest(
                    message=payload.message,
                    history=payload.history,
                    risk_level=assessment.risk_level,
                    needs_professional_support=(
                        assessment.needs_professional_support
                    ),
                )
            )
            reply = generation.reply
            model = generation.model

        saved = await save_exchange(
            client=client,
            request=request,
            user_id=user.user_id,
            session_id=payload.session_id,
            user_message=payload.message,
            assistant_message=reply,
            risk_level=assessment.risk_level,
            model=model,
            request_id=request_id,
        )

        return ChatResponse(
            reply=reply,
            risk_level=assessment.risk_level,
            model=model,
            request_id=request_id,
            session_id=payload.session_id,
            saved=saved,
        )


@app.get(
    "/api/conversations",
    response_model=SavedConversationList,
    tags=["chat"],
)
async def list_saved_conversations(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> SavedConversationList:
    # Saved chats are scoped to the current authenticated user and capped by
    # retention/max_saved_chats settings inside the storage layer.
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
        if fallback_enabled():
            try:
                return demo_store(request).list_conversations(user.user_id)
            except UserNotFoundError as fallback_exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found.",
                ) from fallback_exc
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

        if fallback_enabled():
            try:
                return demo_store(request).get_conversation(
                    user.user_id,
                    session_id,
                )
            except ConversationNotFoundError as fallback_exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Saved conversation not found.",
                ) from fallback_exc

        raise _service_unavailable(exc, request_id) from exc


@app.patch(
    "/api/conversations/{session_id}",
    response_model=SavedConversation,
    tags=["chat"],
)
async def update_saved_conversation_metadata(
    payload: ConversationMetadataUpdate,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    session_id: str = Path(min_length=1, max_length=120),
) -> SavedConversation:
    # Metadata edits currently cover rename, pin, and archive flags. The
    # message history itself is not modified here.
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    client: httpx.AsyncClient = request.app.state.http_client

    try:
        conversation = await patch_model(
            client=client,
            service_name="save-service",
            url=(
                f"{settings.save_service_url}/internal/users/"
                f"{user.user_id}/conversations/{session_id}"
            ),
            payload=payload,
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

        _log_downstream_failure(
            route="update_saved_conversation_metadata",
            request_id=request_id,
            exc=exc,
            fallback_used=fallback_enabled(),
        )
        if fallback_enabled():
            try:
                return demo_store(request).update_conversation_metadata(
                    user.user_id,
                    session_id,
                    payload,
                )
            except ConversationNotFoundError as fallback_exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Saved conversation not found.",
                ) from fallback_exc

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
        if fallback_enabled():
            deleted = demo_store(request).delete_conversation(
                user.user_id,
                session_id,
            )
            return DeleteConversationResponse(deleted=deleted)
        raise _service_unavailable(exc, request_id) from exc


if FRONTEND_INDEX.exists():

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend_app(full_path: str):
        # React owns client-side routes; unknown non-API paths should return the
        # app shell so the browser can render the route.
        return FileResponse(FRONTEND_INDEX)
