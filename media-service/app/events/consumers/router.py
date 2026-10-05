"""Routes an inbound ``lms:events`` message to the right handler. This service consumes two
event types: its own ``media.uploaded`` (drives the transcoder) and catalog-service's
``course.retired`` (drives cleanup) — see the two handler modules for the payload contracts."""

from lms_common.events import Event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.events.consumers.catalog_events import handle_course_retired
from app.events.consumers.pipeline_events import handle_media_uploaded

_HANDLERS = {
    "media.uploaded": handle_media_uploaded,
    "course.retired": handle_course_retired,
}


async def dispatch(db: AsyncSession, settings: Settings, event: Event) -> None:
    handler = _HANDLERS.get(event.event_type)
    if handler is None:
        return  # not one of ours; the stream is shared by every service
    await handler(db, settings, event.payload)
