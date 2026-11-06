"""HTTP client for subscription-service's seat endpoints (see docs/PRODUCT.md §6.1: "Enrol
student -> seat check: Sync learning -> subscription (atomic seat reserve)"). Authenticated
with the shared internal-service token subscription-service checks in its own
``app/api/deps.py::require_seat_caller`` — see that service's README "Not yet wired" for why
this is a shared secret rather than a real service-identity scheme.
"""

from typing import Any

import httpx

from app.core.config import Settings
from app.core.exceptions import BadRequestError, NotFoundError


class SubscriptionServiceError(Exception):
    """subscription-service is unreachable or returned something unexpected."""


def _headers(settings: Settings) -> dict[str, str]:
    return {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN.get_secret_value()}


async def _seat_call(settings: Settings, subscription_id: int, action: str, reservation_key: str) -> dict[str, Any]:
    url = f"{settings.SUBSCRIPTION_SERVICE_URL}/api/v1/subscriptions/{subscription_id}/seats/{action}"
    try:
        async with httpx.AsyncClient(timeout=settings.SUBSCRIPTION_SERVICE_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json={"reservation_key": reservation_key}, headers=_headers(settings))
    except httpx.HTTPError as exc:
        raise SubscriptionServiceError(f"subscription-service is unreachable: {exc}") from exc

    if response.status_code == 404:
        raise NotFoundError("Subscription not found.", code="SUBSCRIPTION_NOT_FOUND")
    if response.status_code == 400:
        body = response.json()
        raise BadRequestError(body.get("message", "The seat request was rejected."), code=body.get("code", "SEAT_REQUEST_REJECTED"))
    if response.status_code >= 400:
        raise SubscriptionServiceError(f"subscription-service returned {response.status_code}: {response.text[:500]}")
    return dict(response.json()["seats"])


async def reserve_seat(settings: Settings, subscription_id: int, reservation_key: str) -> dict[str, Any]:
    return await _seat_call(settings, subscription_id, "reserve", reservation_key)


async def release_seat(settings: Settings, subscription_id: int, reservation_key: str) -> dict[str, Any]:
    return await _seat_call(settings, subscription_id, "release", reservation_key)
