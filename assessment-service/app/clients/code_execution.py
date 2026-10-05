"""code-execution-service's internal API: submit a student's solution to the exam lane, and read a verdict back.

Authenticated with the shared internal service token (the same scheme as subscription-service's seat endpoints; there
is no per-service identity yet). The ``Idempotency-Key`` is the submission's reference, so a retried dispatch never
gets a solution judged twice.
"""

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings


class CodeExecutionRejected(Exception):
    """The request can never succeed (unknown problem, disallowed language, ...): do not retry."""


class CodeExecutionUnavailable(Exception):
    """A transient failure (timeout, 5xx, rate limit): retry later."""


@dataclass(frozen=True, slots=True)
class Verdict:
    submission_id: int
    completed: bool
    verdict: str | None
    passed: int | None
    total: int | None
    score: int | None
    flagged: bool
    similarity_percent: int | None
    similar_to_submission_id: int | None


def _headers(settings: Settings) -> dict[str, str]:
    return {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN.get_secret_value()}


def _verdict(submission: dict[str, Any]) -> Verdict:
    similar = submission.get("similar_to_submission_id")
    return Verdict(
        submission_id=int(submission["submission_id"]),
        completed=submission.get("status") == "completed",
        verdict=submission.get("verdict"),
        passed=submission.get("passed_count"),
        total=submission.get("total_count"),
        score=submission.get("score"),
        flagged=bool(submission.get("flagged", False)),
        similarity_percent=submission.get("similarity_percent"),
        similar_to_submission_id=int(similar) if similar else None,
    )


class CodeExecutionClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.settings.CODE_EXECUTION_URL.rstrip("/"),
            timeout=self.settings.CODE_EXECUTION_TIMEOUT_SECONDS,
            transport=self._transport,
        )

    async def submit(
        self, *, user_id: int, organization_id: int | None, problem_id: int, language: str, source: str, reference: str
    ) -> Verdict:
        body = {
            "user_id": str(user_id),
            "organization_id": str(organization_id) if organization_id else None,
            "problem_id": str(problem_id),
            "language": language,
            "source": source,
            "reference": reference,
            "priority": 2,
        }
        try:
            async with self._client() as client:
                response = await client.post(
                    "/api/v1/internal/submissions", json=body, headers={**_headers(self.settings), "Idempotency-Key": reference}
                )
        except httpx.HTTPError as exc:
            raise CodeExecutionUnavailable(f"code-execution-service unreachable: {exc.__class__.__name__}") from exc
        if response.status_code in (429, 408) or response.status_code >= 500:
            raise CodeExecutionUnavailable(f"code-execution-service answered {response.status_code}")
        if response.status_code >= 400:
            message = ""
            try:
                message = str(response.json().get("message", ""))
            except ValueError:
                pass
            raise CodeExecutionRejected(f"{response.status_code}: {message}"[:280])
        return _verdict(response.json()["submission"])

    async def get(self, submission_id: int) -> Verdict:
        try:
            async with self._client() as client:
                response = await client.get(f"/api/v1/internal/submissions/{submission_id}", headers=_headers(self.settings))
        except httpx.HTTPError as exc:
            raise CodeExecutionUnavailable(f"code-execution-service unreachable: {exc.__class__.__name__}") from exc
        if response.status_code >= 500 or response.status_code == 429:
            raise CodeExecutionUnavailable(f"code-execution-service answered {response.status_code}")
        if response.status_code >= 400:
            raise CodeExecutionRejected(f"{response.status_code}")
        return _verdict(response.json()["submission"])
