"""assessment-service's internal API: pause, resume, terminate a live attempt, and push an integrity decision.

Authenticated with the shared internal service token (there is no per-service identity yet). Every call here is
idempotent on the assessment side, so a retry after a timeout is safe.
"""

import httpx

from app.core.config import Settings


class AssessmentRejected(Exception):
    """The request was understood and refused (unknown attempt, attempt not running, ...): do not retry."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"{status_code}: {message}")
        self.status_code = status_code


class AssessmentUnavailable(Exception):
    """A transient failure (timeout, 5xx): the caller may retry."""


class AssessmentClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    async def _post(self, path: str, body: dict[str, object] | None = None) -> None:
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.ASSESSMENT_SERVICE_URL.rstrip("/"),
                timeout=self.settings.ASSESSMENT_SERVICE_TIMEOUT_SECONDS,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    f"/api/v1/internal/attempts/{path}",
                    json=body or {},
                    headers={"X-Internal-Service-Token": self.settings.INTERNAL_SERVICE_TOKEN.get_secret_value()},
                )
        except httpx.HTTPError as exc:
            raise AssessmentUnavailable(f"assessment-service unreachable: {exc.__class__.__name__}") from exc
        if response.status_code >= 500 or response.status_code == 429:
            raise AssessmentUnavailable(f"assessment-service answered {response.status_code}")
        if response.status_code >= 400:
            message = ""
            try:
                message = str(response.json().get("message", ""))
            except ValueError:
                pass
            raise AssessmentRejected(response.status_code, message[:200])

    async def pause(self, attempt_id: int, reason: str | None) -> None:
        await self._post(f"{attempt_id}/pause", {"reason": reason})

    async def unpause(self, attempt_id: int) -> None:
        await self._post(f"{attempt_id}/unpause")

    async def terminate(self, attempt_id: int, reason: str | None) -> None:
        await self._post(f"{attempt_id}/terminate", {"reason": reason})

    async def integrity(self, attempt_id: int, decision: str) -> None:
        """The synchronous twin of the ``integrity.decided`` event (decision: clear | reviewed_ok | invalidated)."""
        await self._post(f"{attempt_id}/integrity", {"decision": decision})
