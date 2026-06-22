from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Header, HTTPException, status

from app.config import Settings, get_settings
from app.schemas import AuthenticatedUser


def create_access_token(
    user: AuthenticatedUser,
    settings: Settings,
) -> str:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(
        minutes=settings.auth_token_minutes,
    )
    payload = {
        "sub": user.user_id,
        "email": user.email,
        "display_name": user.display_name,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    payload_bytes = _json_b64(payload)
    signature = _sign(payload_bytes, settings.auth_token_secret)
    return f"{payload_bytes}.{signature}"


def get_current_user(
    authorization: str | None = Header(default=None),
) -> AuthenticatedUser:
    settings = get_settings()

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to continue.",
        )

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload_part, signature = token.split(".", 1)
    except ValueError as exc:
        raise _invalid_token() from exc

    expected = _sign(payload_part, settings.auth_token_secret)
    if not hmac.compare_digest(signature, expected):
        raise _invalid_token()

    try:
        payload = _json_unb64(payload_part)
        expires_at = int(payload["exp"])
        user_id = str(payload["sub"])
        email = str(payload["email"])
        display_name = str(payload["display_name"])
    except (KeyError, TypeError, ValueError) as exc:
        raise _invalid_token() from exc

    if datetime.now(timezone.utc).timestamp() >= expires_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session expired. Please sign in again.",
        )

    return AuthenticatedUser(
        user_id=user_id,
        email=email,
        display_name=display_name,
    )


def _json_b64(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _b64url(encoded)


def _json_unb64(value: str) -> dict[str, Any]:
    padding = "=" * (-len(value) % 4)
    decoded = base64.urlsafe_b64decode(f"{value}{padding}")
    parsed = json.loads(decoded)
    if not isinstance(parsed, dict):
        raise ValueError("Token payload must be an object.")
    return parsed


def _sign(payload: str, secret: str) -> str:
    signature = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64url(signature)


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _invalid_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Your session is invalid. Please sign in again.",
    )
