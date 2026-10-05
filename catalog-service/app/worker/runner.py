"""Background worker: relays this service's outbox and consumes events from other services.

Run one or more instances with ``python -m app.worker``.
"""

import asyncio
import logging
import os

from lms_common.events import StreamConsumer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.events.consumers.media_events import dispatch
from app.events.publisher import RedisStreamPublisher, relay_outbox

logger = logging.getLogger("app.worker")


async def run_outbox_relay(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, stop: asyncio.Event) -> None:
    publisher = RedisStreamPublisher(redis, settings)
    while not stop.is_set():
        try:
            published = await relay_outbox(sessionmaker, publisher, batch_size=settings.OUTBOX_BATCH_SIZE)
        except Exception:
            logger.exception("outbox relay iteration failed")
            published = 0
        if not published:
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.WORKER_POLL_SECONDS)
            except TimeoutError:
                pass


async def run_inbound_consumer(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, stop: asyncio.Event) -> None:
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
                    await dispatch(db, event)
                    await db.commit()
                await consumer.ack(event)
        except Exception:
            logger.exception("inbound event consumer iteration failed")
            await asyncio.sleep(settings.WORKER_POLL_SECONDS)


async def run_forever(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, stop: asyncio.Event) -> None:
    logger.info("worker started", extra={"extra_fields": {"pid": os.getpid()}})
    await asyncio.gather(
        run_outbox_relay(sessionmaker, redis, settings, stop),
        run_inbound_consumer(sessionmaker, redis, settings, stop),
    )
    logger.info("worker stopped")
