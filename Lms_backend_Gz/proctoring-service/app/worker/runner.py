"""Background worker: relays this service's outbox, consumes ``lms:events``, analyses snapshots, scores lost heartbeats,
decides finished sessions, and enforces retention. Run one or more instances with ``python -m app.worker`` (rows are
claimed with SKIP LOCKED and a lease, so instances share the work safely)."""

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable

from lms_common.events import StreamConsumer
from redis.asyncio import Redis
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.time import utcnow
from app.events.consumers.router import dispatch
from app.events.publisher import RedisStreamPublisher, relay_outbox
from app.models.session import ProctorEvent, ProctorSession
from app.services.case_service import finalize_sweep
from app.services.processed_event_service import ProcessedEventService
from app.services.session_service import SessionService
from app.services.snapshot_service import SnapshotService, analyze_due

logger = logging.getLogger("app.worker")


async def _idle(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except TimeoutError:
        pass


async def _loop(name: str, step: Callable[[], Awaitable[int]], stop: asyncio.Event, idle_seconds: float) -> None:
    """Run ``step`` until stopped, sleeping only when it found nothing; an exception is logged, never fatal."""
    while not stop.is_set():
        try:
            worked = await step()
        except Exception:
            logger.exception("%s iteration failed", name)
            worked = 0
        if not worked:
            await _idle(stop, idle_seconds)


async def run_inbound_consumer(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, stop: asyncio.Event) -> None:
    consumer = StreamConsumer(
        redis, stream=settings.EVENTS_STREAM, group=settings.EVENTS_CONSUMER_GROUP, name=settings.EVENTS_CONSUMER_NAME, block_ms=settings.EVENTS_BLOCK_MS
    )
    await consumer.ensure_group()
    while not stop.is_set():
        try:
            async for event in consumer.read():
                async with sessionmaker() as db:
                    await dispatch(db, event, settings, redis)
                    await db.commit()
                await consumer.ack(event)
        except Exception:
            logger.exception("inbound event consumer iteration failed")
            await asyncio.sleep(settings.WORKER_POLL_SECONDS)


async def sweep_heartbeats(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings) -> int:
    async with sessionmaker() as db:
        return await SessionService(db, settings, redis).sweep_lost_heartbeats(200)


async def housekeeping(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings) -> None:
    """Retention (docs/PRODUCT.md §5.3: media kept 90 days, then deleted), stale pre-checks, old bookkeeping."""
    async with sessionmaker() as db:
        purged = await SnapshotService(db, settings).purge_expired()
    async with sessionmaker() as db:
        abandoned = await SessionService(db, settings, redis).abandon_stale()
    async with sessionmaker() as db:
        processed = await ProcessedEventService(db).prune(retention_days=settings.PROCESSED_EVENTS_RETENTION_DAYS)
    async with sessionmaker() as db:
        from datetime import timedelta

        from sqlalchemy import select

        old = select(ProctorSession.id).where(ProctorSession.status.in_(["closed", "superseded", "abandoned"]), ProctorSession.updated_at < utcnow() - timedelta(days=settings.EVENTS_RETENTION_DAYS))
        removed = int(getattr(await db.execute(delete(ProctorEvent).where(ProctorEvent.session_id.in_(old))), "rowcount", 0) or 0)
        await db.commit()
    if purged or abandoned or processed or removed:
        logger.info("housekeeping", extra={"extra_fields": {"media_deleted": purged, "sessions_abandoned": abandoned, "processed_events": processed, "old_events": removed}})


async def run_forever(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, stop: asyncio.Event) -> None:
    logger.info("worker started", extra={"extra_fields": {"pid": os.getpid()}})
    publisher = RedisStreamPublisher(redis, settings)
    poll = settings.WORKER_POLL_SECONDS

    async def housekeeping_step() -> int:
        await housekeeping(sessionmaker, redis, settings)
        return 0

    await asyncio.gather(
        _loop("outbox relay", lambda: relay_outbox(sessionmaker, publisher, batch_size=settings.OUTBOX_BATCH_SIZE), stop, poll),
        run_inbound_consumer(sessionmaker, redis, settings, stop),
        _loop("snapshot analysis", lambda: analyze_due(sessionmaker, settings), stop, poll),
        _loop("integrity decisions", lambda: finalize_sweep(sessionmaker, settings), stop, poll),
        _loop("heartbeat sweep", lambda: sweep_heartbeats(sessionmaker, redis, settings), stop, settings.HEARTBEAT_LOST_AFTER_SECONDS / 4),
        _loop("housekeeping", housekeeping_step, stop, settings.HOUSEKEEPING_INTERVAL_SECONDS),
    )
    logger.info("worker stopped")
