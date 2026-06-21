from functools import lru_cache

from fastapi import FastAPI, HTTPException, status

from app.classifier import RiskClassifier
from app.config import get_settings
from app.schemas import RiskAssessment, RiskRequest

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Internal service for deterministic checks, structured risk "
        "classification, and controlled high-risk responses."
    ),
)


@lru_cache
def get_classifier() -> RiskClassifier:
    return RiskClassifier(settings)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {
        "service": "safety-service",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post(
    "/internal/classify",
    response_model=RiskAssessment,
    tags=["internal"],
)
async def classify(payload: RiskRequest) -> RiskAssessment:
    try:
        return await get_classifier().classify(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Safety classification failed.",
        ) from exc
