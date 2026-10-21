"""Routes an inbound ``lms:events`` message to the right handler. See the two handler modules
for the payload contracts this service consumes from user-management and catalog-service."""

from lms_common.events import Event
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.consumers.access_events import handle_course_access_expired, handle_course_access_granted
from app.events.consumers.assessment_events import handle_attempt_finalized
from app.events.consumers.catalog_events import handle_course_published, handle_course_retired
from app.events.consumers.institution_events import handle_institution_deleted, handle_institution_upserted

_HANDLERS = {
    "institution.created": handle_institution_upserted,
    "institution.updated": handle_institution_upserted,
    "institution.suspended": handle_institution_upserted,
    "institution.activated": handle_institution_upserted,
    "institution.deleted": handle_institution_deleted,
    "course.published": handle_course_published,
    "course.retired": handle_course_retired,
    "attempt.finalized": handle_attempt_finalized,
    "course_access.granted": handle_course_access_granted,
    "course_access.extended": handle_course_access_granted,
    "course_access.expired": handle_course_access_expired,
}


async def dispatch(db: AsyncSession, event: Event) -> None:
    handler = _HANDLERS.get(event.event_type)
    if handler is None:
        return  # not one of ours; the stream is shared by every service
    await handler(db, event.payload)
