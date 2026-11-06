"""Background worker: relays this service's outbox, consumes ``lms:events`` (``user.*``), flags SLA breaches, auto-closes
resolved tickets nobody answered, and prunes de-duplication records. Run one or more instances with
``python -m app.worker`` (rows are claimed with SKIP LOCKED and a lease)."""

import asyncio
import logging
import os

from lms_common.events import StreamConsumer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.events.consumers.router import dispatch
from app.events.publisher import RedisStreamPublisher, relay_outbox
from app.services.processed_event_service import ProcessedEventService
from app.services.ticket_service import sweep_sla

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
                    await dispatch(db, event, settings)
                    await db.commit()
                await consumer.ack(event)
        except Exception:
            logger.exception("inbound event consumer iteration failed")
            await asyncio.sleep(settings.WORKER_POLL_SECONDS)


async def run_sla_loop(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            async with sessionmaker() as db:
                changed = await sweep_sla(db, settings)
            if changed:
                logger.info("sla sweep", extra={"extra_fields": {"changed": changed}})
        except Exception:
            logger.exception("sla sweep failed")
        await _idle(stop, settings.SLA_SWEEP_SECONDS)


async def housekeeping_once(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings) -> int:
    """Prune de-duplication records (tickets themselves are kept)."""
    async with sessionmaker() as db:
        return await ProcessedEventService(db).prune(retention_days=settings.PROCESSED_EVENTS_RETENTION_DAYS)


async def run_housekeeping(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            pruned = await housekeeping_once(sessionmaker, settings)
            if pruned:
                logger.info("housekeeping", extra={"extra_fields": {"pruned_processed_events": pruned}})
        except Exception:
            logger.exception("housekeeping failed")
        await _idle(stop, settings.HOUSEKEEPING_INTERVAL_SECONDS)


async def run_forever(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, stop: asyncio.Event) -> None:
    logger.info("worker started", extra={"extra_fields": {"pid": os.getpid()}})
    await asyncio.gather(
        run_outbox_relay(sessionmaker, redis, settings, stop),
        run_inbound_consumer(sessionmaker, redis, settings, stop),
        run_sla_loop(sessionmaker, settings, stop),
        run_housekeeping(sessionmaker, settings, stop),
    )
    logger.info("worker stopped")
