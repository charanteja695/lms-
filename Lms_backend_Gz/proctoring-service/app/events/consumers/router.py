"""What this service consumes from ``lms:events`` (payload contracts of the producers, all from assessment-service):

  test.published / test.retired   {"test_id", "title", "kind", "proctoring_level", "organization_id" (the owning employer or
                                  null for the platform), ...}                          -> which tests are proctored, at what level
  attempt.started                 {"attempt_id", "test_id", "user_id", "organization_id", "proctoring_level", ...}
                                                                                          -> link the pre-checked session, go active
  attempt.submitted               {"attempt_id", "proctoring_level", "submit_reason", ...} -> end the session, queue the decision

Every event is applied at most once per ``event_id`` (delivery is at-least-once and an integrity decision must not be
taken twice); the handlers are also idempotent on their own keys.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from lms_common.events import Event
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.session import TestRef
from app.services.processed_event_service import ProcessedEventService
from app.services.session_service import SessionService

Handler = Callable[[AsyncSession, Settings, Redis | None, dict[str, Any]], Awaitable[None]]


async def _test_published(db: AsyncSession, settings: Settings, redis: Redis | None, payload: dict[str, Any]) -> None:
    test_id = int(payload["test_id"])
    ref = await db.get(TestRef, test_id)
    if ref is None:
        ref = TestRef(test_id=test_id, title="", kind="", proctoring_level="none")
        db.add(ref)
    ref.title, ref.kind = payload.get("title") or ref.title, payload.get("kind") or ref.kind
    ref.proctoring_level = payload.get("proctoring_level") or "none"
    ref.screen_share = ref.proctoring_level == "strict" and bool(payload.get("proctoring_screen_share"))
    ref.owner_organization_id = int(payload["organization_id"]) if payload.get("organization_id") else None
    ref.retired = False


async def _test_retired(db: AsyncSession, settings: Settings, redis: Redis | None, payload: dict[str, Any]) -> None:
    ref = await db.get(TestRef, int(payload["test_id"]))
    if ref is not None:
        ref.retired = True  # sessions already running are unaffected


async def _attempt_started(db: AsyncSession, settings: Settings, redis: Redis | None, payload: dict[str, Any]) -> None:
    await SessionService(db, settings, redis).on_attempt_started(payload)


async def _attempt_submitted(db: AsyncSession, settings: Settings, redis: Redis | None, payload: dict[str, Any]) -> None:
    await SessionService(db, settings, redis).on_attempt_submitted(payload)


_HANDLERS: dict[str, Handler] = {
    "test.published": _test_published,
    "test.retired": _test_retired,
    "attempt.started": _attempt_started,
    "attempt.submitted": _attempt_submitted,
}


async def dispatch(db: AsyncSession, event: Event, settings: Settings, redis: Redis | None = None) -> None:
    """Handle ``event`` in ``db``'s transaction; the caller commits."""
    handler = _HANDLERS.get(event.event_type)
    if handler is None:
        return  # not one of ours; the stream is shared by every service
    if not await ProcessedEventService(db).claim(event.event_id):
        return  # a redelivery
    await handler(db, settings, redis, event.payload)
