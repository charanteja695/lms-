"""Routes an inbound ``lms:events`` message to its handler, at most once per ``event_id``.

Delivery on the stream is at-least-once and a result must never be applied twice, so every handled event is recorded
in ``processed_events`` in the same transaction as its effects. See the handler modules for the payload contracts.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from lms_common.events import Event
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.events.consumers import attempt_events, directory_events
from app.services.processed_event_service import ProcessedEventService

Handler = Callable[[AsyncSession, Settings, Redis | None, dict[str, Any]], Awaitable[None]]


def _plain(handler: Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]) -> Handler:
    async def wrapped(db: AsyncSession, _settings: Settings, _redis: Redis | None, payload: dict[str, Any]) -> None:
        await handler(db, payload)

    return wrapped


_HANDLERS: dict[str, Handler] = {
    "enrollment.created": _plain(directory_events.handle_enrollment_created),
    "enrollment.removed": _plain(directory_events.handle_enrollment_removed),
    "course.eligible_for_final": _plain(directory_events.handle_eligible_for_final),
    "course.published": _plain(directory_events.handle_course_published),
    "course.retired": _plain(directory_events.handle_course_retired),
    "submission.judged": attempt_events.handle_submission_judged,
    "integrity.flagged": attempt_events.handle_integrity_flagged,
    "integrity.decided": attempt_events.handle_integrity_decided,
}


async def dispatch(db: AsyncSession, event: Event, settings: Settings, redis: Redis | None = None) -> None:
    """Handle ``event`` in ``db``'s transaction; the caller commits."""
    handler = _HANDLERS.get(event.event_type)
    if handler is None:
        return  # not one of ours; the stream is shared by every service
    if not await ProcessedEventService(db).claim(event.event_id):
        return  # a redelivery
    await handler(db, settings, redis, event.payload)
