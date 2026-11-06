"""Background worker: relays this service's outbox, consumes ``lms:events``, sends pending emails
and prunes old de-duplication records.

Run one or more instances with ``python -m app.worker``.
"""

import asyncio
import logging
import os

from lms_common.events import StreamConsumer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.channels.email import EmailSender, build_email_sender
from app.core.config import Settings
from app.events.consumers.router import dispatch
from app.events.publisher import RedisStreamPublisher, relay_outbox
from app.services.delivery_service import deliver_due
from app.services.processed_event_service import ProcessedEventService

logger = logging.getLogger("app.worker")


async def _idle(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except TimeoutError:
        pass


async def run_outbox_relay(
    sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, stop: asyncio.Event
) -> None:
    publisher = RedisStreamPublisher(redis, settings)
    while not stop.is_set():
        try:
            published = await relay_outbox(sessionmaker, publisher, batch_size=settings.OUTBOX_BATCH_SIZE)
        except Exception:
            logger.exception("outbox relay iteration failed")
            published = 0
        if not published:
            await _idle(stop, settings.WORKER_POLL_SECONDS)


async def run_inbound_consumer(
    sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, stop: asyncio.Event
) -> None:
    consumer = StreamConsumer(
        redis,
        stream=settings.EVENTS_STREAM,
        group=settings.EVENTS_CONSUMER_GROUP,
        name=settings.EVENTS_CONSUMER_NAME,
        block_ms=settings.EVENTS_BLOCK_MS,
    )
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


async def run_delivery_loop(
    sessionmaker: async_sessionmaker[AsyncSession], sender: EmailSender, settings: Settings, stop: asyncio.Event
) -> None:
    while not stop.is_set():
        try:
            attempted = await deliver_due(sessionmaker, sender, settings)
        except Exception:
            logger.exception("delivery sweep failed")
            attempted = 0
        if not attempted:
            await _idle(stop, settings.WORKER_POLL_SECONDS)


async def run_housekeeping(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            async with sessionmaker() as db:
                pruned = await ProcessedEventService(db).prune(retention_days=settings.PROCESSED_EVENTS_RETENTION_DAYS)
            if pruned:
                logger.info("pruned processed events", extra={"extra_fields": {"count": pruned}})
        except Exception:
            logger.exception("housekeeping failed")
        await _idle(stop, settings.HOUSEKEEPING_INTERVAL_SECONDS)


async def run_forever(
    sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, stop: asyncio.Event
) -> None:
    logger.info("worker started", extra={"extra_fields": {"pid": os.getpid()}})
    await asyncio.gather(
        run_outbox_relay(sessionmaker, redis, settings, stop),
        run_inbound_consumer(sessionmaker, redis, settings, stop),
        run_delivery_loop(sessionmaker, build_email_sender(settings), settings, stop),
        run_housekeeping(sessionmaker, settings, stop),
    )
    logger.info("worker stopped")
