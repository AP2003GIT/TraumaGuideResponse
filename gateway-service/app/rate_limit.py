from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException, Request, status


_REQUESTS: dict[str, Deque[float]] = defaultdict(deque)


def check_rate_limit(
    request: Request,
    *,
    bucket: str,
    max_requests: int,
    window_seconds: int,
) -> None:
    now = time.monotonic()
    identity = _client_identity(request)
    key = f"{bucket}:{identity}"
    attempts = _REQUESTS[key]

    while attempts and now - attempts[0] > window_seconds:
        attempts.popleft()

    if len(attempts) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a moment and try again.",
        )

    attempts.append(now)


def _client_identity(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()

    if request.client:
        return request.client.host

    return "unknown"
