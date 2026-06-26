from pathlib import Path

from app.local_demo import LocalDemoStore
from app.schemas import (
    ConversationMetadataUpdate,
    RegisterRequest,
    SaveTurnRequest,
)


def create_store(path: Path) -> LocalDemoStore:
    return LocalDemoStore(
        retention_days=10,
        max_saved_chats=10,
        admin_emails=["admin@example.com"],
        storage_path=str(path),
    )


def test_local_demo_store_persists_users_chats_and_metadata(
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "local-demo-data.json"
    store = create_store(data_path)
    user = store.create_user(
        RegisterRequest(
            display_name="Admin",
            email="admin@example.com",
            password="test-password",
        )
    )

    store.save_turn(
        user.user_id,
        "session-1",
        SaveTurnRequest(
            user_message="Hello",
            assistant_message="I hear you.",
            risk_level="standard",
            model="single-service-demo",
            request_id="request-1",
        ),
    )
    store.update_conversation_metadata(
        user.user_id,
        "session-1",
        ConversationMetadataUpdate(title="Renamed", pinned=True),
    )

    restored = create_store(data_path)
    restored_user = restored.get_user(user.user_id)
    restored_conversation = restored.get_conversation(
        user.user_id,
        "session-1",
    )

    assert restored_user.role == "admin"
    assert restored_conversation.title == "Renamed"
    assert restored_conversation.pinned is True
    assert len(restored_conversation.messages) == 2
