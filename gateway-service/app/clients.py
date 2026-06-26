from typing import Any

import httpx
from pydantic import BaseModel, ValidationError


class DownstreamServiceError(RuntimeError):
    """Raised when a downstream service request fails."""
    def __init__(
        self,
        service: str,
        message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.service = service
        self.status_code = status_code


# These helpers wrap HTTP calls to safety/chat/save services. They convert
# network failures, non-2xx responses, and schema mismatches into one exception
# type that the gateway route handlers can process consistently.
async def post_model(
    *,
    client: httpx.AsyncClient,
    service_name: str,
    url: str,
    payload: BaseModel,
    response_model: type[BaseModel],
    request_id: str,
) -> BaseModel:
    try:
        response = await client.post(
            url,
            json=payload.model_dump(mode="json"),
            headers={"X-Request-ID": request_id},
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise DownstreamServiceError(
            service_name,
            f"{service_name} timed out.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        detail: Any
        try:
            detail = exc.response.json()
        except ValueError:
            detail = exc.response.text

        raise DownstreamServiceError(
            service_name,
            f"{service_name} returned {exc.response.status_code}: {detail}",
            status_code=exc.response.status_code,
        ) from exc
    except httpx.HTTPError as exc:
        raise DownstreamServiceError(
            service_name,
            f"{service_name} is unavailable.",
        ) from exc

    try:
        return response_model.model_validate(response.json())
    except (ValueError, ValidationError) as exc:
        raise DownstreamServiceError(
            service_name,
            f"{service_name} returned an invalid response contract.",
        ) from exc


async def get_model(
    *,
    client: httpx.AsyncClient,
    service_name: str,
    url: str,
    response_model: type[BaseModel],
    request_id: str,
) -> BaseModel:
    try:
        response = await client.get(
            url,
            headers={"X-Request-ID": request_id},
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise DownstreamServiceError(
            service_name,
            f"{service_name} timed out.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        detail: Any
        try:
            detail = exc.response.json()
        except ValueError:
            detail = exc.response.text

        raise DownstreamServiceError(
            service_name,
            f"{service_name} returned {exc.response.status_code}: {detail}",
            status_code=exc.response.status_code,
        ) from exc
    except httpx.HTTPError as exc:
        raise DownstreamServiceError(
            service_name,
            f"{service_name} is unavailable.",
        ) from exc

    try:
        return response_model.model_validate(response.json())
    except (ValueError, ValidationError) as exc:
        raise DownstreamServiceError(
            service_name,
            f"{service_name} returned an invalid response contract.",
        ) from exc


async def delete_model(
    *,
    client: httpx.AsyncClient,
    service_name: str,
    url: str,
    response_model: type[BaseModel],
    request_id: str,
) -> BaseModel:
    try:
        response = await client.delete(
            url,
            headers={"X-Request-ID": request_id},
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise DownstreamServiceError(
            service_name,
            f"{service_name} timed out.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        detail: Any
        try:
            detail = exc.response.json()
        except ValueError:
            detail = exc.response.text

        raise DownstreamServiceError(
            service_name,
            f"{service_name} returned {exc.response.status_code}: {detail}",
            status_code=exc.response.status_code,
        ) from exc
    except httpx.HTTPError as exc:
        raise DownstreamServiceError(
            service_name,
            f"{service_name} is unavailable.",
        ) from exc

    try:
        return response_model.model_validate(response.json())
    except (ValueError, ValidationError) as exc:
        raise DownstreamServiceError(
            service_name,
            f"{service_name} returned an invalid response contract.",
        ) from exc


async def patch_model(
    *,
    client: httpx.AsyncClient,
    service_name: str,
    url: str,
    payload: BaseModel,
    response_model: type[BaseModel],
    request_id: str,
) -> BaseModel:
    try:
        response = await client.patch(
            url,
            json=payload.model_dump(mode="json", exclude_none=True),
            headers={"X-Request-ID": request_id},
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise DownstreamServiceError(
            service_name,
            f"{service_name} timed out.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        detail: Any
        try:
            detail = exc.response.json()
        except ValueError:
            detail = exc.response.text

        raise DownstreamServiceError(
            service_name,
            f"{service_name} returned {exc.response.status_code}: {detail}",
            status_code=exc.response.status_code,
        ) from exc
    except httpx.HTTPError as exc:
        raise DownstreamServiceError(
            service_name,
            f"{service_name} is unavailable.",
        ) from exc

    try:
        return response_model.model_validate(response.json())
    except (ValueError, ValidationError) as exc:
        raise DownstreamServiceError(
            service_name,
            f"{service_name} returned an invalid response contract.",
        ) from exc


async def get_health(
    *,
    client: httpx.AsyncClient,
    url: str,
) -> str:
    # Simple status-only health check used by older callers.
    try:
        response = await client.get(url)
        response.raise_for_status()
        return "healthy"
    except httpx.HTTPError:
        return "unavailable"


async def get_health_detail(
    *,
    client: httpx.AsyncClient,
    url: str,
) -> tuple[str, str | None]:
    # Richer health check used by admin diagnostics and the service chip.
    try:
        response = await client.get(url)
        response.raise_for_status()
        return "healthy", None
    except httpx.TimeoutException:
        return "unavailable", "Health check timed out."
    except httpx.HTTPStatusError as exc:
        return (
            "unavailable",
            f"Health check returned {exc.response.status_code}.",
        )
    except httpx.HTTPError as exc:
        return "unavailable", str(exc) or "Health check failed."
