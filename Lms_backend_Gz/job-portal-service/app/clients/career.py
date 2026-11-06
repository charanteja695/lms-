"""career-service's internal API: freeze the resume a candidate applies with, so what the recruiter judges cannot change afterwards."""

from dataclasses import dataclass
from typing import Any

import httpx

from app.clients.errors import Rejected, Unavailable
from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class ResumeSnapshot:
    resume_id: int
    version_no: int
    title: str
    document: dict[str, Any]
    ats_score: int | None


class CareerClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    async def snapshot(self, *, resume_id: int, user_id: int, label: str) -> ResumeSnapshot:
        headers = {"X-Internal-Service-Token": self.settings.INTERNAL_SERVICE_TOKEN.get_secret_value()}
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.CAREER_SERVICE_URL.rstrip("/"), timeout=self.settings.CAREER_SERVICE_TIMEOUT_SECONDS, transport=self._transport
            ) as client:
                response = await client.post(f"/api/v1/internal/resumes/{resume_id}/snapshot", json={"user_id": str(user_id), "label": label}, headers=headers)
        except httpx.HTTPError as exc:
            raise Unavailable(f"career-service unreachable: {exc.__class__.__name__}") from exc
        if response.status_code in (408, 429) or response.status_code >= 500:
            raise Unavailable(f"career-service answered {response.status_code}")
        if response.status_code >= 400:
            print(f"[DEBUG CAREER SNAPSHOT] URL: {response.request.url} Status: {response.status_code} Response: {response.text}")
            raise Rejected(f"career-service answered {response.status_code}", status=response.status_code)
        body = response.json()
        return ResumeSnapshot(resume_id=resume_id, version_no=int(body["version_no"]), title=str(body["title"]), document=dict(body["document"]), ats_score=body.get("ats_score"))
