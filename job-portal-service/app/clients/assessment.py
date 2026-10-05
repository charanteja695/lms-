"""assessment-service's internal API: invite a shortlisted candidate to the job's hiring test."""

from datetime import datetime
from typing import Any

import httpx

from app.clients.errors import Rejected, Unavailable
from app.core.config import Settings


def _code(response: httpx.Response) -> str | None:
    try:
        return str(response.json().get("code"))
    except (ValueError, AttributeError):
        return None


class AssessmentClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    async def invite(self, *, test_id: int, user_id: int, reference: str, opens_at: datetime, expires_at: datetime, max_attempts: int | None = 1) -> dict[str, Any]:
        """Invite ``user_id`` to hiring test ``test_id``. assessment-service creates *or updates* the invitation, so a retry is safe."""
        body = {
            "test_id": str(test_id), "user_id": str(user_id), "reference": reference, "opens_at": opens_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"), "max_attempts": max_attempts,
        }
        headers = {"X-Internal-Service-Token": self.settings.INTERNAL_SERVICE_TOKEN.get_secret_value()}
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.ASSESSMENT_SERVICE_URL.rstrip("/"), timeout=self.settings.ASSESSMENT_SERVICE_TIMEOUT_SECONDS, transport=self._transport
            ) as client:
                response = await client.post("/api/v1/internal/assignments", json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise Unavailable(f"assessment-service unreachable: {exc.__class__.__name__}") from exc
        if response.status_code in (408, 429) or response.status_code >= 500:
            raise Unavailable(f"assessment-service answered {response.status_code}")
        if response.status_code >= 400:
            raise Rejected(f"assessment-service answered {response.status_code}", status=response.status_code, code=_code(response))
        return dict(response.json().get("assignment") or {})
