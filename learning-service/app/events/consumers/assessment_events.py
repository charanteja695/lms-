"""Test results from assessment-service.

  attempt.finalized  {"enrollment_id", "test_id", "test_kind": "topic" | "module" | "final" | ..., "result":
                      "passed" | "failed" | "invalidated", "percent", "attempt_id", "revision", ...}

Only topic and module tests gate completion (the final test is the certificate's business: ``course.passed``). A
student may pass a test on a later attempt; a pass then stays until an integrity case invalidates it. The handler is an
idempotent upsert ordered by ``revision``, so a redelivered or reordered event changes nothing.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.progress_service import ProgressService

_GATING_KINDS = {"topic", "module"}


async def handle_attempt_finalized(db: AsyncSession, payload: dict[str, Any]) -> None:
    if payload.get("test_kind") not in _GATING_KINDS or not payload.get("enrollment_id"):
        return
    await ProgressService(db).apply_test_result(
        enrollment_public_id=int(payload["enrollment_id"]),
        test_id=int(payload["test_id"]),
        attempt_id=int(payload["attempt_id"]),
        result=str(payload["result"]),
        percent=float(payload.get("percent") or 0.0),
        revision=int(payload.get("revision") or 1),
    )
