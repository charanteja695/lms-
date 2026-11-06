"""Routes an inbound ``lms:events`` message to its handler, at most once per ``event_id`` (delivery is at-least-once).
See app/events/consumers/handlers.py for the payload contracts."""

from collections.abc import Awaitable, Callable
from typing import Any

from lms_common.events import Event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.events.consumers import handlers
from app.services.processed_event_service import ProcessedEventService

Handler = Callable[[AsyncSession, Settings, dict[str, Any]], Awaitable[None]]

_HANDLERS: dict[str, Handler] = {
    "course.published": handlers.handle_course_published,
    "course.retired": handlers.handle_course_retired,
    "transcript.ready": handlers.handle_transcript_ready,
    "enrollment.created": handlers.handle_enrollment_created,
    "enrollment.removed": handlers.handle_enrollment_removed,
    "attempt.started": handlers.handle_attempt_started,
    "attempt.submitted": handlers.handle_attempt_submitted,
    "attempt.finalized": handlers.handle_attempt_finalized,
    "certificate.issued": handlers.handle_certificate_issued,
    "certificate.revoked": handlers.handle_certificate_revoked,
}


async def dispatch(db: AsyncSession, event: Event, settings: Settings) -> None:
    """Handle ``event`` in ``db``'s transaction; the caller commits."""
    handler = _HANDLERS.get(event.event_type)
    if handler is None:
        return  # not one of ours; the stream is shared by every service
    if not await ProcessedEventService(db).claim(event.event_id):
        return  # a redelivery
    await handler(db, settings, event.payload)
