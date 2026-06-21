from datetime import datetime, timezone

import pytest

from app.schemas import SaveTurnRequest
from app.storage import ChatStore, ConversationNotFoundError


def test_save_and_load_conversation(tmp_path) -> None:
    store = ChatStore(str(tmp_path / "chats.sqlite3"), retention_days=10)
    store.initialize()

    saved = store.save_turn(
        "session-1",
        SaveTurnRequest(
            user_message="I feel overwhelmed.",
            assistant_message="Try a grounding exercise.",
            risk_level="standard",
            model="demo-model",
            request_id="request-1",
        ),
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert saved.session_id == "session-1"
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


def test_expired_conversation_is_removed(tmp_path) -> None:
    store = ChatStore(str(tmp_path / "chats.sqlite3"), retention_days=1)
    store.initialize()

    store.save_turn(
        "session-1",
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
            "session-1",
            now=datetime(2026, 1, 3, tzinfo=timezone.utc),
        )
