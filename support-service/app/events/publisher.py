"""Relay this service's own outbox to the Redis Stream other services read (see
lms-backend/README.md §5). Delivery is at-least-once: consumers de-duplicate on ``event_id``."""

import json
import logging
from typing import Protocol

from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.time import utcnow
from app.models.outbox_event import OutboxEvent

logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    async def publish(self, event: OutboxEvent) -> None: ...


class RedisStreamPublisher:
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self.redis = redis
        self.stream = settings.EVENTS_STREAM
        self.max_length = settings.EVENTS_STREAM_MAX_LENGTH

    async def publish(self, event: OutboxEvent) -> None:
        await self.redis.xadd(
            self.stream,
            {
                "event_id": event.id.hex,
                "event_type": event.event_type,
                "aggregate_type": event.aggregate_type,
                "occurred_time": event.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "payload": json.dumps(event.payload, separators=(",", ":"), ensure_ascii=False),
            },
            maxlen=self.max_length,
            approximate=True,
        )


async def relay_outbox(sessionmaker: async_sessionmaker[AsyncSession], publisher: EventPublisher, *, batch_size: int) -> int:
    """Publish one batch of pending events in creation order. Safe to run on several workers at once."""
    async with sessionmaker() as db:
        events = list(
            (
                await db.execute(select(OutboxEvent).where(OutboxEvent.published_at.is_(None)).order_by(OutboxEvent.created_at, OutboxEvent.id).limit(batch_size).with_for_update(skip_locked=True))
            ).scalars()
        )
        published = 0
        for event in events:
            try:
                await publisher.publish(event)
            except Exception:
                logger.exception("Event publishing failed; will retry", extra={"extra_fields": {"event": event.event_type}})
                await db.execute(update(OutboxEvent).where(OutboxEvent.id == event.id).values(attempts=OutboxEvent.attempts + 1))
                break  # keep ordering: retry this event before any later one
            event.published_at = utcnow()
            published += 1
        await db.commit()
        return published
