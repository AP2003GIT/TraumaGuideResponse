from app.gemini_service import build_contents
from app.schemas import ChatGenerationRequest, ChatMessage


def test_history_roles_are_converted_for_gemini() -> None:
    request = ChatGenerationRequest(
        message="What did I say?",
        history=[
            ChatMessage(role="user", content="My name is Aleksa."),
            ChatMessage(role="assistant", content="Hello Aleksa."),
        ],
        risk_level="standard",
        needs_professional_support=False,
    )

    contents = build_contents(request)

    assert [item.role for item in contents] == [
        "user",
        "model",
        "user",
    ]
