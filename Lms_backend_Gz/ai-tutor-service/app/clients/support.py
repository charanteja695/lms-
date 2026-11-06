"""support-service's internal API: open a ticket for a student the tutor is handing to a person.

The ``Idempotency-Key`` is the escalation's public id, so a retry after a timeout (the ticket may already exist) never
opens a second ticket for the same hand-off.
"""

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings


class SupportRejected(Exception):
    """The request can never succeed as sent (a validation error): do not retry."""


class SupportUnavailable(Exception):
    """A timeout, a 5xx or a rate limit: retry later."""


@dataclass(frozen=True, slots=True)
class TicketRef:
    ticket_id: int


class SupportClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    async def create_ticket(self, payload: dict[str, Any], *, idempotency_key: str) -> TicketRef:
        headers = {"X-Internal-Service-Token": self.settings.INTERNAL_SERVICE_TOKEN.get_secret_value(), "Idempotency-Key": idempotency_key}
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.SUPPORT_SERVICE_URL.rstrip("/"), timeout=self.settings.SUPPORT_SERVICE_TIMEOUT_SECONDS, transport=self._transport
            ) as client:
                response = await client.post("/api/v1/internal/tickets", json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise SupportUnavailable(f"support-service unreachable: {exc.__class__.__name__}") from exc
        if response.status_code in (408, 429) or response.status_code >= 500:
            raise SupportUnavailable(f"support-service answered {response.status_code}")
        if response.status_code >= 400:
            raise SupportRejected(f"support-service answered {response.status_code}: {response.text[:200]}")
        return TicketRef(ticket_id=int(response.json()["ticket"]["ticket_id"]))
