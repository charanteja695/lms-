"""ai-tutor-service's internal API: the transcript of the tutor conversation a ticket was handed off from.

Only called after this service has decided the agent may see the ticket; ai-tutor trusts the internal token.
"""

from typing import Any

import httpx

from app.core.config import Settings


class TutorUnavailable(Exception):
    """A timeout, a 5xx, or the tutor not answering at all."""


class TranscriptNotFound(Exception):
    """ai-tutor no longer has the conversation (deleted by the student)."""


class TutorClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    async def transcript(self, conversation_id: str) -> dict[str, Any]:
        headers = {"X-Internal-Service-Token": self.settings.INTERNAL_SERVICE_TOKEN.get_secret_value()}
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.AI_TUTOR_SERVICE_URL.rstrip("/"), timeout=self.settings.AI_TUTOR_TIMEOUT_SECONDS, transport=self._transport
            ) as client:
                response = await client.get(f"/api/v1/internal/conversations/{conversation_id}", headers=headers)
        except httpx.HTTPError as exc:
            raise TutorUnavailable(f"ai-tutor-service unreachable: {exc.__class__.__name__}") from exc
        if response.status_code == 404:
            raise TranscriptNotFound(conversation_id)
        if response.status_code >= 400:
            raise TutorUnavailable(f"ai-tutor-service answered {response.status_code}")
        conversation: dict[str, Any] = response.json()["conversation"]
        return conversation
