"""Routes an inbound ``lms:events`` message to its handler, at most once per ``event_id``.

Delivery on the stream is at-least-once, and a repeated event must not send a second email, so
every handled event is recorded in ``processed_events`` in the same transaction as its effects.
See the handler modules for the payload contracts this service consumes."""

from collections.abc import Awaitable, Callable

from lms_common.events import Event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.events.consumers.directory_events import handle_course_published, handle_user_deleted, handle_user_upserted
from app.events.consumers.notification_events import (
    handle_course_request_decided,
    handle_eligible_for_final,
    handle_enrollment_created,
    handle_enrollment_removed,
    handle_subscription_activated,
    handle_subscription_cancelled,
    handle_subscription_expired,
)
from app.services.processed_event_service import ProcessedEventService

Handler = Callable[[AsyncSession, Event, Settings], Awaitable[None]]

_HANDLERS: dict[str, Handler] = {
    "user.created": handle_user_upserted,
    "user.updated": handle_user_upserted,
    "user.suspended": handle_user_upserted,
    "user.activated": handle_user_upserted,
    "user.deleted": handle_user_deleted,
    "course.published": handle_course_published,
    "enrollment.created": handle_enrollment_created,
    "enrollment.removed": handle_enrollment_removed,
    "course.eligible_for_final": handle_eligible_for_final,
    "course_request.decided": handle_course_request_decided,
    "subscription.activated": handle_subscription_activated,
    "subscription.cancelled": handle_subscription_cancelled,
    "subscription.expired": handle_subscription_expired,
}


async def dispatch(db: AsyncSession, event: Event, settings: Settings) -> None:
    """Handle ``event`` in ``db``'s transaction; the caller commits."""
    handler = _HANDLERS.get(event.event_type)
    if handler is None:
        return  # not one of ours; the stream is shared by every service
    if not await ProcessedEventService(db).claim(event.event_id):
        return  # a redelivery
    await handler(db, event, settings)
