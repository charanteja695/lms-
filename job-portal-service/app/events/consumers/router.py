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
    "user.created": handlers.handle_user_upserted,
    "user.updated": handlers.handle_user_upserted,
    "user.suspended": handlers.handle_user_upserted,
    "user.activated": handlers.handle_user_upserted,
    "user.deleted": handlers.handle_user_deleted,
    "institution.created": handlers.handle_org_upserted,
    "institution.updated": handlers.handle_org_upserted,
    "institution.suspended": handlers.handle_org_upserted,
    "institution.activated": handlers.handle_org_upserted,
    "institution.deleted": handlers.handle_org_deleted,
    "employer.created": handlers.handle_org_upserted,
    "employer.updated": handlers.handle_org_upserted,
    "employer.suspended": handlers.handle_org_upserted,
    "employer.activated": handlers.handle_org_upserted,
    "employer.deleted": handlers.handle_org_deleted,
    "course.published": handlers.handle_course_published,
    "skill_profile.updated": handlers.handle_skill_profile_updated,
    "attempt.finalized": handlers.handle_attempt_finalized,
    "interview.completed": handlers.handle_interview_completed,
}


async def dispatch(db: AsyncSession, event: Event, settings: Settings) -> None:
    """Handle ``event`` in ``db``'s transaction; the caller commits."""
    handler = _HANDLERS.get(event.event_type)
    if handler is None:
        return  # not one of ours; the stream is shared by every service
    if not await ProcessedEventService(db).claim(event.event_id):
        return  # a redelivery
    await handler(db, settings, event.payload)
