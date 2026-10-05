"""Idempotent consumer for the ``lms:events`` Redis Stream, using a consumer group.

A consumer group lets several instances of one service split the stream without duplicating
work between instances, while still tolerating at-least-once redelivery (a crash before ack
redelivers the same message). Callers must still treat their own handler as idempotent — the
same event can arrive twice across restarts or rebalances — typically by keying a "processed
events" table on ``event_id`` inside the same transaction as the handler's side effect.

    consumer = StreamConsumer(redis, stream="lms:events", group="catalog-service", name="worker-1")
    await consumer.ensure_group()
    async for event in consumer.read():
        await handle(event)          # idempotent: safe to run twice for the same event_id
        await consumer.ack(event)

**Redelivery.** A message whose handler raised, or whose worker died before acking, stays in the group's pending list.
Every ``read()`` therefore first *reclaims* messages that have sat unacked for ``redeliver_after_ms`` (``XAUTOCLAIM``: it
does not matter which consumer name held them, so a crashed instance's work is picked up by any other). A message that
keeps failing is not retried forever: after ``max_deliveries`` attempts it is moved to a dead-letter stream
(``<stream>:dead``, with the delivery count) and acknowledged, so one poison message cannot block or spin a service.
Watch that stream's length: anything in it is an event some service could not process.
"""

import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from lms_common.events.envelope import Event

logger = logging.getLogger(__name__)


class StreamConsumer:
    def __init__(
        self,
        redis: Redis,
        *,
        stream: str,
        group: str,
        name: str,
        block_ms: int = 5_000,
        batch_size: int = 100,
        redeliver_after_ms: int = 60_000,
        max_deliveries: int = 10,
        reclaim_every_seconds: float = 5.0,
        dead_stream: str | None = None,
    ) -> None:
        self.redis = redis
        self.stream = stream
        self.group = group
        self.name = name
        self.block_ms = block_ms
        self.batch_size = batch_size
        self.redeliver_after_ms = redeliver_after_ms
        self.max_deliveries = max_deliveries
        self.reclaim_every_seconds = reclaim_every_seconds
        self.dead_stream = dead_stream or f"{stream}:dead"
        self._ids_by_event: dict[str, str] = {}
        self._last_reclaim = 0.0

    async def ensure_group(self) -> None:
        """Create the consumer group at the end of the stream if it doesn't exist yet."""
        try:
            await self.redis.xgroup_create(self.stream, self.group, id="$", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def read(self) -> AsyncIterator[Event]:
        """Yield events once: first any that were delivered earlier but never acked (see the module note), then new ones.
        Call in a loop; each call blocks up to ``block_ms`` waiting for new events."""
        for event in await self._reclaim():
            yield event
        response = await self.redis.xreadgroup(
            self.group, self.name, {self.stream: ">"}, count=self.batch_size, block=self.block_ms
        )
        for _stream_name, messages in response or []:
            for stream_id, fields in messages:
                fresh = await self._parse(stream_id, fields, deliveries=1)
                if fresh is not None:
                    yield fresh

    async def _reclaim(self) -> list[Event]:
        now = time.monotonic()
        if now - self._last_reclaim < self.reclaim_every_seconds:
            return []
        self._last_reclaim = now
        result: Any = await self.redis.xautoclaim(
            self.stream, self.group, self.name, min_idle_time=self.redeliver_after_ms, start_id="0-0", count=self.batch_size
        )
        events: list[Event] = []
        for stream_id, fields in result[1]:
            if not fields:  # the entry was trimmed from the stream while pending: nothing left to deliver
                await self.redis.xack(self.stream, self.group, stream_id)
                continue
            deliveries = await self._deliveries(stream_id)
            if deliveries > self.max_deliveries:
                await self._dead_letter(stream_id, fields, deliveries, "too many failed deliveries")
                continue
            event = await self._parse(stream_id, fields, deliveries)
            if event is not None:
                events.append(event)
        return events

    async def _parse(self, stream_id: str, fields: dict[str, str], deliveries: int) -> Event | None:
        try:
            event = Event.from_stream_fields(fields)
        except (KeyError, ValueError, TypeError) as exc:  # not an event we can ever read: retrying cannot help
            await self._dead_letter(stream_id, fields, deliveries, f"malformed: {exc.__class__.__name__}")
            return None
        self._ids_by_event[event.event_id] = stream_id
        return event

    async def _deliveries(self, stream_id: str) -> int:
        rows: Any = await self.redis.xpending_range(self.stream, self.group, min=stream_id, max=stream_id, count=1)
        return int(rows[0]["times_delivered"]) if rows else 0

    async def _dead_letter(self, stream_id: str, fields: dict[str, str], deliveries: int, reason: str) -> None:
        record: dict[str, str] = {**fields, "stream_id": stream_id, "group": self.group, "deliveries": str(deliveries), "reason": reason}
        await self.redis.xadd(self.dead_stream, record)  # type: ignore[arg-type]
        await self.redis.xack(self.stream, self.group, stream_id)
        logger.error(
            "Event moved to the dead-letter stream after %s deliveries (%s)", deliveries, reason,
            extra={"extra_fields": {"stream": self.stream, "group": self.group, "stream_id": stream_id}},
        )

    async def ack(self, event: Event) -> None:
        stream_id = self._ids_by_event.pop(event.event_id, None)
        if stream_id is not None:
            await self.redis.xack(self.stream, self.group, stream_id)
