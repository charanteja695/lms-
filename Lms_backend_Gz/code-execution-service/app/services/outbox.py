"""Write a transactional outbox row in the same DB transaction as the change that caused it.
The worker relays unpublished rows to Redis Stream ``lms:events`` (see app/events/publisher.py)."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox_event import OutboxEvent


def write_event(db: AsyncSession, *, event_type: str, aggregate_id: uuid.UUID, payload: dict[str, Any]) -> None:
    db.add(OutboxEvent(event_type=event_type, aggregate_type="submission", aggregate_id=aggregate_id, payload=payload))
