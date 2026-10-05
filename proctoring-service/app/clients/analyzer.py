"""The AI analysis worker's contract (docs/PRODUCT.md §5.3: "AI detection: no face / multiple faces / different person /
phone or book visible / looking away / audio anomaly"). Detection is not built into this service: any HTTP service that
implements this contract (an in-house model server, or a wrapper over a vision provider behind ai-gateway) plugs in via
``AI_ANALYZER_URL``.

    POST {AI_ANALYZER_URL}/analyze
    {"snapshot_id", "session_id", "kind": "periodic"|"screen"|"audio"|"face_enrol"|"id_photo", "level",
     "media_url": "<short-lived presigned GET>", "reference_url": "<presigned GET of the student's reference photo>" | null}
    -> 200 {"findings": [{"type": "no_face"|"multiple_faces"|"different_person"|"identity_mismatch"|"phone_detected"|
                            "book_detected"|"looking_away"|"voices_detected", "confidence": 0.0-1.0, "detail": {...}?}]}

An empty list means "looked, found nothing". A finding below ``AI_MIN_CONFIDENCE`` is recorded but scores nothing. The
same findings can instead be pushed asynchronously to ``POST /internal/snapshots/{id}/findings``.
"""

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings


class AnalyzerRejected(Exception):
    """The analyzer refused this media (unreadable image, ...): do not retry."""


class AnalyzerUnavailable(Exception):
    """Timeout or 5xx: retry later."""


@dataclass(frozen=True, slots=True)
class Finding:
    type: str
    confidence: float
    detail: dict[str, Any] | None = None


class AnalyzerClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.settings.AI_ANALYZER_URL)

    async def analyze(
        self, *, snapshot_id: int, session_id: int, kind: str, level: str, media_url: str, reference_url: str | None
    ) -> list[Finding]:
        headers = {}
        if self.settings.AI_ANALYZER_TOKEN is not None:
            headers["Authorization"] = f"Bearer {self.settings.AI_ANALYZER_TOKEN.get_secret_value()}"
        try:
            async with httpx.AsyncClient(
                base_url=str(self.settings.AI_ANALYZER_URL).rstrip("/"), timeout=self.settings.AI_ANALYZER_TIMEOUT_SECONDS, transport=self._transport
            ) as client:
                response = await client.post(
                    "/analyze",
                    json={
                        "snapshot_id": str(snapshot_id), "session_id": str(session_id), "kind": kind, "level": level,
                        "media_url": media_url, "reference_url": reference_url,
                    },
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise AnalyzerUnavailable(f"analyzer unreachable: {exc.__class__.__name__}") from exc
        if response.status_code >= 500 or response.status_code == 429:
            raise AnalyzerUnavailable(f"analyzer answered {response.status_code}")
        if response.status_code >= 400:
            raise AnalyzerRejected(f"analyzer answered {response.status_code}")
        return [
            Finding(str(item["type"]), float(item.get("confidence", 0)), item.get("detail"))
            for item in response.json().get("findings", [])
        ]
