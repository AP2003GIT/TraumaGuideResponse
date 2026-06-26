from fastapi.testclient import TestClient

from app.main import app
from app.schemas import DependencyStatus


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_dependency_status_includes_mode_and_details() -> None:
    status = DependencyStatus(
        gateway="healthy",
        safety_service="unavailable",
        chat_service="healthy",
        save_service="healthy",
        mode="fallback",
        fallback_enabled=True,
        checked_at="2026-01-01T00:00:00+00:00",
        details={"safety_service": "Health check timed out."},
    )

    assert status.mode == "fallback"
    assert status.fallback_enabled is True
    assert status.details["safety_service"] == "Health check timed out."
