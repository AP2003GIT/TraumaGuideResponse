from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Request, status

from app.config import get_settings
from app.schemas import (
    AccountExport,
    AuthRequest,
    AuthenticatedUser,
    DeleteConversationResponse,
    DeleteUserDataResponse,
    RegisterRequest,
    SavedConversation,
    SavedConversationList,
    SaveTurnRequest,
)
from app.storage import (
    AccountAlreadyExistsError,
    ChatStore,
    ConversationNotFoundError,
    InvalidCredentialsError,
    UserNotFoundError,
)

settings = get_settings()
SessionId = Annotated[str, Path(min_length=1, max_length=120)]
UserId = Annotated[str, Path(min_length=1, max_length=120)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = ChatStore(
        database_url=settings.database_url,
        retention_days=settings.chat_retention_days,
        max_saved_chats=settings.chat_max_saved_chats,
    )
    store.initialize()
    app.state.chat_store = store
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Internal service that stores chat sessions locally and "
        "expires them after the configured retention window."
    ),
    lifespan=lifespan,
)


def get_store(request: Request) -> ChatStore:
    return request.app.state.chat_store


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {
        "service": "save-service",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["system"])
async def health(request: Request) -> dict[str, str]:
    try:
        get_store(request).health_check()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from exc

    return {"status": "healthy"}


@app.post(
    "/internal/auth/register",
    response_model=AuthenticatedUser,
    tags=["internal"],
)
async def register_user(
    payload: RegisterRequest,
    request: Request,
) -> AuthenticatedUser:
    try:
        return get_store(request).create_user(payload)
    except AccountAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        ) from exc


@app.post(
    "/internal/auth/login",
    response_model=AuthenticatedUser,
    tags=["internal"],
)
async def login_user(
    payload: AuthRequest,
    request: Request,
) -> AuthenticatedUser:
    try:
        return get_store(request).authenticate_user(payload)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        ) from exc


@app.get(
    "/internal/users/{user_id}",
    response_model=AuthenticatedUser,
    tags=["internal"],
)
async def get_user(
    user_id: UserId,
    request: Request,
) -> AuthenticatedUser:
    try:
        return get_store(request).get_user(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        ) from exc


@app.get(
    "/internal/users/{user_id}/export",
    response_model=AccountExport,
    tags=["internal"],
)
async def export_user_data(
    user_id: UserId,
    request: Request,
) -> AccountExport:
    try:
        return get_store(request).export_user_data(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        ) from exc


@app.delete(
    "/internal/users/{user_id}",
    response_model=DeleteUserDataResponse,
    tags=["internal"],
)
async def delete_user_data(
    user_id: UserId,
    request: Request,
) -> DeleteUserDataResponse:
    deleted, deleted_conversations = get_store(request).delete_user_data(
        user_id,
    )
    return DeleteUserDataResponse(
        deleted=deleted,
        deleted_conversations=deleted_conversations,
    )


@app.post(
    "/internal/users/{user_id}/conversations/{session_id}/turns",
    response_model=SavedConversation,
    tags=["internal"],
)
async def save_turn(
    user_id: UserId,
    session_id: SessionId,
    payload: SaveTurnRequest,
    request: Request,
) -> SavedConversation:
    try:
        return get_store(request).save_turn(user_id, session_id, payload)
    except (ConversationNotFoundError, UserNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved conversation not found.",
        ) from exc


@app.get(
    "/internal/users/{user_id}/conversations",
    response_model=SavedConversationList,
    tags=["internal"],
)
async def list_conversations(
    user_id: UserId,
    request: Request,
) -> SavedConversationList:
    return get_store(request).list_conversations(user_id)


@app.get(
    "/internal/users/{user_id}/conversations/{session_id}",
    response_model=SavedConversation,
    tags=["internal"],
)
async def get_conversation(
    user_id: UserId,
    session_id: SessionId,
    request: Request,
) -> SavedConversation:
    try:
        return get_store(request).get_conversation(user_id, session_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved conversation not found.",
        ) from exc


@app.delete(
    "/internal/users/{user_id}/conversations/{session_id}",
    response_model=DeleteConversationResponse,
    tags=["internal"],
)
async def delete_conversation(
    user_id: UserId,
    session_id: SessionId,
    request: Request,
) -> DeleteConversationResponse:
    deleted = get_store(request).delete_conversation(user_id, session_id)
    return DeleteConversationResponse(deleted=deleted)
