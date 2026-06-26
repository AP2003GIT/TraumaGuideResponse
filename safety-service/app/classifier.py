from google import genai
from google.genai import types

from app.config import Settings
from app.prompts import RISK_CLASSIFIER_PROMPT
from app.responses import controlled_response
from app.schemas import (
    ModelRiskAssessment,
    RiskAssessment,
    RiskRequest,
)

IMMEDIATE_PHRASES = (
    "i am going to kill myself now",
    "i'm going to kill myself now",
    "i will kill myself tonight",
    "i have a plan to kill myself",
    "i am about to kill myself",
    "i'm about to kill myself",
    "i am going to hurt someone now",
    "i have a plan to hurt someone",
    "ubiću se večeras",
    "ubicu se veceras",
    "upravo ću se ubiti",
    "upravo cu se ubiti",
    "imam plan da se ubijem",
    "sada ću se ubiti",
    "sada cu se ubiti",
)

EXAMPLE_MARKERS = (
    "fictional user",
    "software testing",
    "for testing only",
    "hypothetical example",
    "quoted example",
)


def contains_immediate_phrase(message: str) -> bool:
    normalized = " ".join(message.lower().split())

    if any(marker in normalized for marker in EXAMPLE_MARKERS):
        return False

    return any(phrase in normalized for phrase in IMMEDIATE_PHRASES)


def build_classifier_input(request: RiskRequest) -> str:
    lines: list[str] = []

    for message in request.history:
        lines.append(f"{message.role.upper()}: {message.content}")

    lines.append(f"NEWEST USER MESSAGE: {request.message}")
    return "\n".join(lines)


class RiskClassifier:
    """Classifies incoming messages into safety risk levels."""
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = (
            genai.Client(api_key=settings.gemini_api_key)
            if settings.gemini_api_key
            else None
        )

    async def classify(self, request: RiskRequest) -> RiskAssessment:
        if contains_immediate_phrase(request.message):
            return RiskAssessment(
                risk_level="immediate",
                mentions_self_harm=True,
                mentions_harm_to_others=False,
                needs_professional_support=True,
                brief_reason=(
                    "The newest message explicitly indicates immediate "
                    "self-harm intent or planning."
                ),
                safe_reply=controlled_response(
                    "immediate",
                    request.message,
                ),
            )

        if self.client is None:
            raise RuntimeError(
                "GEMINI_API_KEY is missing from the safety service."
            )

        response = await self.client.aio.models.generate_content(
            model=self.settings.safety_model,
            contents=build_classifier_input(request),
            config=types.GenerateContentConfig(
                system_instruction=RISK_CLASSIFIER_PROMPT,
                temperature=0,
                response_mime_type="application/json",
                response_json_schema=(
                    ModelRiskAssessment.model_json_schema()
                ),
            ),
        )

        response_text = (response.text or "").strip()
        if not response_text:
            raise RuntimeError(
                "Gemini returned an empty safety classification."
            )

        model_assessment = ModelRiskAssessment.model_validate_json(
            response_text
        )

        return RiskAssessment(
            **model_assessment.model_dump(),
            safe_reply=controlled_response(
                model_assessment.risk_level,
                request.message,
            ),
        )
