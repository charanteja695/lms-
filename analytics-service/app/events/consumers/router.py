"""Routes every inbound ``lms:events`` message to the ingestion pipeline, at most once per ``event_id``
(delivery is at-least-once). Unlike most services here, there is no per-event-type handler map: every event
type is a candidate for ingestion, and app/ingest/extract.py's registry decides what (if anything) is kept —
see its module docstring for the full list and why."""

from lms_common.events import Event
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ingest_service import ingest
from app.services.processed_event_service import ProcessedEventService


async def dispatch(db: AsyncSession, event: Event) -> None:
    """Handle ``event`` in ``db``'s transaction; the caller commits."""
    if not await ProcessedEventService(db).claim(event.event_id):
        return  # a redelivery
    await ingest(db, event_id=event.event_id, event_type=event.event_type, occurred_time=event.occurred_time, payload=event.payload)
