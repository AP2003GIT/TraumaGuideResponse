import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.schemas import (
    AuthRequest,
    ConversationMetadataUpdate,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    SaveTurnRequest,
)
from app.storage import ChatStore, ConversationNotFoundError


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="Set TEST_DATABASE_URL to run PostgreSQL storage tests.",
)


def create_store() -> ChatStore:
    assert TEST_DATABASE_URL is not None
    return ChatStore(
        TEST_DATABASE_URL,
        retention_days=10,
        max_saved_chats=10,
    )


def create_user(store: ChatStore) -> str:
    user = store.create_user(
        RegisterRequest(
            display_name="Test User",
            email=f"test-{uuid4()}@example.com",
            password="test-password",
        )
    )
    return user.user_id


def test_save_and_load_conversation() -> None:
    store = create_store()
    store.initialize()
    user_id = create_user(store)
    session_id = f"test-{uuid4()}"

    saved = store.save_turn(
        user_id,
        session_id,
        SaveTurnRequest(
            user_message="I feel overwhelmed.",
            assistant_message="Try a grounding exercise.",
            risk_level="standard",
            model="demo-model",
            request_id="request-1",
        ),
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert saved.session_id == session_id
    assert saved.retention_days == 10
    assert saved.expires_at == datetime(
        2026,
        1,
        11,
        tzinfo=timezone.utc,
    )
    assert [message.role for message in saved.messages] == [
        "user",
        "assistant",
    ]
    assert saved.messages[1].risk_level == "standard"
    assert saved.messages[1].model == "demo-model"


def test_conversation_metadata_can_be_updated() -> None:
    store = create_store()
    store.initialize()
    user_id = create_user(store)
    session_id = f"test-{uuid4()}"

    store.save_turn(
        user_id,
        session_id,
        SaveTurnRequest(
            user_message="Hello.",
            assistant_message="Hello back.",
            risk_level="standard",
            model=None,
            request_id="request-1",
        ),
    )

    updated = store.update_conversation_metadata(
        user_id,
        session_id,
        ConversationMetadataUpdate(title="Renamed chat", pinned=True),
    )
    listed = store.list_conversations(user_id)

    assert updated.title == "Renamed chat"
    assert updated.pinned is True
    assert listed.conversations[0].title == "Renamed chat"
    assert listed.conversations[0].pinned is True


def test_expired_conversation_is_removed() -> None:
    assert TEST_DATABASE_URL is not None
    store = ChatStore(
        TEST_DATABASE_URL,
        retention_days=1,
        max_saved_chats=10,
    )
    store.initialize()
    user_id = create_user(store)
    session_id = f"test-{uuid4()}"

    store.save_turn(
        user_id,
        session_id,
        SaveTurnRequest(
            user_message="Hello.",
            assistant_message="Hello back.",
            risk_level="standard",
            model=None,
            request_id="request-1",
        ),
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(ConversationNotFoundError):
        store.get_conversation(
            user_id,
            session_id,
            now=datetime(2026, 1, 3, tzinfo=timezone.utc),
        )


def test_oldest_conversations_are_pruned() -> None:
    assert TEST_DATABASE_URL is not None
    store = ChatStore(
        TEST_DATABASE_URL,
        retention_days=10,
        max_saved_chats=2,
    )
    store.initialize()
    user_id = create_user(store)
    prefix = f"test-{uuid4()}"

    for index in range(3):
        store.save_turn(
            user_id,
            f"{prefix}-{index}",
            SaveTurnRequest(
                user_message=f"Hello {index}.",
                assistant_message=f"Hello back {index}.",
                risk_level="standard",
                model=None,
                request_id=f"request-{index}",
            ),
            now=datetime(2026, 1, index + 1, tzinfo=timezone.utc),
        )

    with pytest.raises(ConversationNotFoundError):
        store.get_conversation(
            user_id,
            f"{prefix}-0",
            now=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )

    assert (
        store.get_conversation(
            user_id,
            f"{prefix}-1",
            now=datetime(2026, 1, 4, tzinfo=timezone.utc),
        ).session_id
        == f"{prefix}-1"
    )
    assert (
        store.get_conversation(
            user_id,
            f"{prefix}-2",
            now=datetime(2026, 1, 4, tzinfo=timezone.utc),
        ).session_id
        == f"{prefix}-2"
    )


def test_profile_update_and_password_reset() -> None:
    store = create_store()
    store.initialize()
    email = f"test-{uuid4()}@example.com"
    user = store.create_user(
        RegisterRequest(
            display_name="Original",
            email=email,
            password="test-password",
        )
    )

    updated = store.update_user_profile(
        user.user_id,
        ProfileUpdateRequest(
            display_name="Updated",
            email=email,
            current_password="test-password",
            new_password="updated-password",
        ),
    )

    assert updated.display_name == "Updated"
    assert (
        store.authenticate_user(
            AuthRequest(email=email, password="updated-password")
        ).user_id
        == user.user_id
    )

    reset_request = store.request_password_reset(
        PasswordResetRequest(email=email)
    )
    assert reset_request.dev_reset_token

    reset_user = store.confirm_password_reset(
        PasswordResetConfirmRequest(
            reset_token=reset_request.dev_reset_token,
            new_password="reset-password",
        )
    )

    assert reset_user.user_id == user.user_id
    assert (
        store.authenticate_user(
            AuthRequest(email=email, password="reset-password")
        ).user_id
        == user.user_id
    )


def test_admin_summary_counts_storage() -> None:
    store = create_store()
    store.initialize()
    user_id = create_user(store)
    session_id = f"test-{uuid4()}"

    store.save_turn(
        user_id,
        session_id,
        SaveTurnRequest(
            user_message="Hello.",
            assistant_message="Hello back.",
            risk_level="standard",
            model=None,
            request_id="request-1",
        ),
    )

    summary = store.admin_summary()

    assert summary.users >= 1
    assert summary.conversations >= 1
    assert summary.messages >= 2


def test_admin_email_receives_admin_role() -> None:
    assert TEST_DATABASE_URL is not None
    email = f"admin-{uuid4()}@example.com"
    store = ChatStore(
        TEST_DATABASE_URL,
        retention_days=10,
        max_saved_chats=10,
        admin_emails=[email],
    )
    store.initialize()

    user = store.create_user(
        RegisterRequest(
            display_name="Admin User",
            email=email,
            password="test-password",
        )
    )

    assert user.role == "admin"
    assert (
        store.authenticate_user(
            AuthRequest(email=email, password="test-password")
        ).role
        == "admin"
    )
