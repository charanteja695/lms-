"""Background worker: relays this service's outbox, consumes ``lms:events`` into `EventFact` rows, recomputes
the trailing `DailyRollup` window, runs due scheduled reports, and prunes old data. Run one or more instances
with ``python -m app.worker`` (each does its own work independently; rollup/report ticks are cheap to repeat)."""

import asyncio
import logging
import os
from datetime import timedelta

from lms_common.events import StreamConsumer
from redis.asyncio import Redis
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.aggregations.rollup import recompute_days
from app.core.config import Settings
from app.core.time import utcnow
from app.events.consumers.router import dispatch
from app.events.publisher import RedisStreamPublisher, relay_outbox
from app.models.fact import EventFact
from app.services.processed_event_service import ProcessedEventService
from app.services.report_service import run_due_reports

logger = logging.getLogger("app.worker")


async def _idle(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except TimeoutError:
        pass


async def run_outbox_relay(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, stop: asyncio.Event) -> None:
    publisher = RedisStreamPublisher(redis, settings)
    while not stop.is_set():
        try:
            published = await relay_outbox(sessionmaker, publisher, batch_size=settings.OUTBOX_BATCH_SIZE)
        except Exception:
            logger.exception("outbox relay iteration failed")
            published = 0
        if not published:
            await _idle(stop, settings.WORKER_POLL_SECONDS)


async def run_inbound_consumer(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, stop: asyncio.Event) -> None:
    consumer = StreamConsumer(redis, stream=settings.EVENTS_STREAM, group=settings.EVENTS_CONSUMER_GROUP, name=settings.EVENTS_CONSUMER_NAME, block_ms=settings.EVENTS_BLOCK_MS)
    await consumer.ensure_group()
    while not stop.is_set():
        try:
            async for event in consumer.read():
                async with sessionmaker() as db:
                    await dispatch(db, event)
                    await db.commit()
                await consumer.ack(event)
        except Exception:
            logger.exception("inbound event consumer iteration failed")
            await asyncio.sleep(settings.WORKER_POLL_SECONDS)


async def rollup_tick(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings) -> int:
    today = utcnow().date()
    days = [today - timedelta(days=n) for n in range(settings.ROLLUP_TAIL_DAYS + 1)]
    async with sessionmaker() as db:
        return await recompute_days(db, days)


async def run_rollups(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            rows = await rollup_tick(sessionmaker, settings)
            logger.info("rollup tick", extra={"extra_fields": {"rows": rows}})
        except Exception:
            logger.exception("rollup tick failed")
        await _idle(stop, settings.ROLLUP_INTERVAL_SECONDS)


async def run_reports(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            ran = await run_due_reports(sessionmaker, settings)
            if ran:
                logger.info("reports run", extra={"extra_fields": {"count": ran}})
        except Exception:
            logger.exception("report tick failed")
        await _idle(stop, settings.REPORT_CHECK_INTERVAL_SECONDS)


async def housekeeping_once(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings) -> tuple[int, int]:
    """Prune de-duplication records and raw `EventFact` rows past retention (rollups, already computed, are kept)."""
    async with sessionmaker() as db:
        pruned_events = await ProcessedEventService(db).prune(retention_days=settings.PROCESSED_EVENTS_RETENTION_DAYS)
    async with sessionmaker() as db:
        result = await db.execute(delete(EventFact).where(EventFact.ingested_at < utcnow() - timedelta(days=settings.RAW_EVENT_RETENTION_DAYS)))
        await db.commit()
        return pruned_events, int(getattr(result, "rowcount", 0) or 0)


async def run_housekeeping(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            pruned, facts = await housekeeping_once(sessionmaker, settings)
            if pruned or facts:
                logger.info("housekeeping", extra={"extra_fields": {"pruned_processed_events": pruned, "pruned_event_facts": facts}})
        except Exception:
            logger.exception("housekeeping failed")
        await _idle(stop, settings.HOUSEKEEPING_INTERVAL_SECONDS)


async def run_forever(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, stop: asyncio.Event) -> None:
    logger.info("worker started", extra={"extra_fields": {"pid": os.getpid()}})
    await asyncio.gather(
        run_outbox_relay(sessionmaker, redis, settings, stop),
        run_inbound_consumer(sessionmaker, redis, settings, stop),
        run_rollups(sessionmaker, settings, stop),
        run_reports(sessionmaker, settings, stop),
        run_housekeeping(sessionmaker, settings, stop),
    )
    logger.info("worker stopped")
