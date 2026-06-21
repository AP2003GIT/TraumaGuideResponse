from google import genai
from google.genai import types

from app.config import Settings
from app.prompts import SUPPORT_SYSTEM_PROMPT
from app.schemas import (
    ChatGenerationRequest,
    ChatGenerationResponse,
)


def build_contents(
    request: ChatGenerationRequest,
) -> list[types.Content]:
    contents: list[types.Content] = []

    for message in request.history:
        role = "model" if message.role == "assistant" else "user"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=message.content)],
            )
        )

    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=request.message)],
        )
    )

    return contents


class GeminiChatService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = (
            genai.Client(api_key=settings.gemini_api_key)
            if settings.gemini_api_key
            else None
        )

    async def generate(
        self,
        request: ChatGenerationRequest,
    ) -> ChatGenerationResponse:
        if self.client is None:
            raise RuntimeError(
                "GEMINI_API_KEY is missing from the chat service."
            )

        if request.risk_level == "elevated":
            risk_context = (
                "\n\nThe independent safety service classified the newest "
                "message as elevated distress. Be especially gentle, avoid "
                "alarming language, and encourage appropriate real-world "
                "professional support."
            )
        else:
            risk_context = (
                "\n\nThe independent safety service classified the newest "
                "message as standard risk. Provide ordinary supportive "
                "psychoeducation within the stated boundaries."
            )

        response = await self.client.aio.models.generate_content(
            model=self.settings.chat_model,
            contents=build_contents(request),
            config=types.GenerateContentConfig(
                system_instruction=(
                    SUPPORT_SYSTEM_PROMPT + risk_context
                ),
                temperature=0.4,
            ),
        )

        reply = (response.text or "").strip()
        if not reply:
            raise RuntimeError(
                "Gemini returned an empty chat response."
            )

        return ChatGenerationResponse(
            reply=reply,
            model=self.settings.chat_model,
        )
