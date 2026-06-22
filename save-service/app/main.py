from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Request, status

from app.config import get_settings
from app.schemas import (
    DeleteConversationResponse,
    SavedConversation,
    SavedConversationList,
    SaveTurnRequest,
)
from app.storage import ChatStore, ConversationNotFoundError

settings = get_settings()
SessionId = Annotated[str, Path(min_length=1, max_length=120)]


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
    "/internal/conversations/{session_id}/turns",
    response_model=SavedConversation,
    tags=["internal"],
)
async def save_turn(
    session_id: SessionId,
    payload: SaveTurnRequest,
    request: Request,
) -> SavedConversation:
    return get_store(request).save_turn(session_id, payload)


@app.get(
    "/internal/conversations",
    response_model=SavedConversationList,
    tags=["internal"],
)
async def list_conversations(request: Request) -> SavedConversationList:
    return get_store(request).list_conversations()


@app.get(
    "/internal/conversations/{session_id}",
    response_model=SavedConversation,
    tags=["internal"],
)
async def get_conversation(
    session_id: SessionId,
    request: Request,
) -> SavedConversation:
    try:
        return get_store(request).get_conversation(session_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved conversation not found.",
        ) from exc


@app.delete(
    "/internal/conversations/{session_id}",
    response_model=DeleteConversationResponse,
    tags=["internal"],
)
async def delete_conversation(
    session_id: SessionId,
    request: Request,
) -> DeleteConversationResponse:
    deleted = get_store(request).delete_conversation(session_id)
    return DeleteConversationResponse(deleted=deleted)
