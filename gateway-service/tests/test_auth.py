import pytest
from fastapi import HTTPException

from app.auth import create_access_token, get_current_user, require_admin_user
from app.config import get_settings
from app.schemas import AuthenticatedUser


def test_access_token_preserves_user_role() -> None:
    settings = get_settings()
    user = AuthenticatedUser(
        user_id="user-1",
        email="person@example.com",
        display_name="Person",
        role="admin",
    )

    token = create_access_token(user, settings)
    parsed = get_current_user(f"Bearer {token}")

    assert parsed.role == "admin"


def test_require_admin_user_rejects_standard_user() -> None:
    settings = get_settings()
    user = AuthenticatedUser(
        user_id="user-1",
        email="person@example.com",
        display_name="Person",
        role="user",
    )

    token = create_access_token(user, settings)

    with pytest.raises(HTTPException) as exc_info:
        require_admin_user(f"Bearer {token}")

    assert exc_info.value.status_code == 403
