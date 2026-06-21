from typing import Any

import httpx
from pydantic import BaseModel, ValidationError


class DownstreamServiceError(RuntimeError):
    def __init__(
        self,
        service: str,
        message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.service = service
        self.status_code = status_code


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


async def get_health(
    *,
    client: httpx.AsyncClient,
    url: str,
) -> str:
    try:
        response = await client.get(url)
        response.raise_for_status()
        return "healthy"
    except httpx.HTTPError:
        return "unavailable"
