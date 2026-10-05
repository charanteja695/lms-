"""Events that move an attempt forward.

  submission.judged   code-execution-service: {"reference": "attempt:<attempt id>:<question id>", "submission_id",
                      "verdict", "passed", "total", "score", "flagged", "similarity_percent", ...}
  integrity.flagged   proctoring-service: {"attempt_id", "status": "flagged" | "under_review"}
  integrity.decided   proctoring-service: {"attempt_id", "decision": "clear" | "reviewed_ok" | "invalidated"}
                      ("clear" is the automatic low-risk outcome; the other two follow a human review — a human always
                      confirms an invalidation)
"""

from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.ids import parse_public_id
from app.services.coding_service import handle_judged_event
from app.services.result_service import ResultService


async def handle_submission_judged(db: AsyncSession, settings: Settings, redis: Redis | None, payload: dict[str, Any]) -> None:
    await handle_judged_event(db, settings, redis, payload)


async def handle_integrity_flagged(db: AsyncSession, settings: Settings, redis: Redis | None, payload: dict[str, Any]) -> None:
    attempt_id = parse_public_id(payload.get("attempt_id"))
    if attempt_id is not None:
        await ResultService(db, settings, redis).integrity_flagged(attempt_id, under_review=payload.get("status") == "under_review")


async def handle_integrity_decided(db: AsyncSession, settings: Settings, redis: Redis | None, payload: dict[str, Any]) -> None:
    attempt_id = parse_public_id(payload.get("attempt_id"))
    if attempt_id is not None:
        await ResultService(db, settings, redis).integrity_decided(attempt_id, str(payload.get("decision")))
