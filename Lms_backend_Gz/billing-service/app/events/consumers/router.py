"""Routes an inbound ``lms:events`` message to its handler, at most once per ``event_id`` (delivery is at-least-once).
See app/events/consumers/handlers.py for the payload contracts."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from lms_common.events import Event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.events.consumers import handlers
from app.services.processed_event_service import ProcessedEventService

Handler = Callable[[AsyncSession, Settings, dict[str, Any], datetime], Awaitable[None]]

_HANDLERS: dict[str, Handler] = {
    f"{kind}.{change}": handlers.handle_org_upserted for kind in ("institution", "employer") for change in ("created", "updated", "suspended", "activated")
} | {
    "institution.deleted": handlers.handle_org_deleted,
    "employer.deleted": handlers.handle_org_deleted,
    "subscription.activated": handlers.handle_subscription_activated,
}


async def dispatch(db: AsyncSession, event: Event, settings: Settings) -> None:
    """Handle ``event`` in ``db``'s transaction; the caller commits."""
    handler = _HANDLERS.get(event.event_type)
    if handler is None:
        return  # not one of ours; the stream is shared by every service
    if not await ProcessedEventService(db).claim(event.event_id):
        return  # a redelivery
    await handler(db, settings, event.payload, event.occurred_time)
