"""Background worker: relays this service's outbox, consumes ``lms:events``, embeds newly published course content, opens
support tickets for escalations, and prunes old conversations and de-duplication records. Run one or more instances with
``python -m app.worker`` (rows are claimed with SKIP LOCKED and a lease)."""

import asyncio
import logging
import os
from datetime import timedelta

from lms_common.events import StreamConsumer
from redis.asyncio import Redis
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.gateway import GatewayClient
from app.clients.support import SupportClient
from app.core.config import Settings
from app.core.time import utcnow
from app.events.consumers.router import dispatch
from app.events.publisher import RedisStreamPublisher, relay_outbox
from app.models.conversation import Conversation
from app.services.escalation_service import deliver_due
from app.services.index_service import index_due
from app.services.processed_event_service import ProcessedEventService

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


async def run_index_loop(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, stop: asyncio.Event) -> None:
    gateway = GatewayClient(settings)
    while not stop.is_set():
        try:
            worked = await index_due(sessionmaker, settings, gateway)
        except Exception:
            logger.exception("indexing sweep failed")
            worked = 0
        if not worked:
            await _idle(stop, settings.WORKER_POLL_SECONDS)


async def run_escalation_loop(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, stop: asyncio.Event) -> None:
    gateway, support = GatewayClient(settings), SupportClient(settings)
    while not stop.is_set():
        try:
            worked = await deliver_due(sessionmaker, settings, gateway, support)
        except Exception:
            logger.exception("escalation sweep failed")
            worked = 0
        if not worked:
            await _idle(stop, settings.WORKER_POLL_SECONDS)


async def housekeeping_once(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings) -> tuple[int, int]:
    """Prune de-duplication records, and hard-delete conversations a student deleted (after a week's grace) or that are
    older than ``CONVERSATION_RETENTION_DAYS`` (messages, feedback and escalations go with them)."""
    async with sessionmaker() as db:
        pruned_events = await ProcessedEventService(db).prune(retention_days=settings.PROCESSED_EVENTS_RETENTION_DAYS)
    async with sessionmaker() as db:
        now = utcnow()
        result = await db.execute(
            delete(Conversation).where(
                (Conversation.deleted_at < now - timedelta(days=7)) | (Conversation.created_at < now - timedelta(days=settings.CONVERSATION_RETENTION_DAYS))
            )
        )
        await db.commit()
        return pruned_events, int(getattr(result, "rowcount", 0) or 0)


async def run_housekeeping(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            events, conversations = await housekeeping_once(sessionmaker, settings)
            if events or conversations:
                logger.info("housekeeping", extra={"extra_fields": {"pruned_processed_events": events, "deleted_conversations": conversations}})
        except Exception:
            logger.exception("housekeeping failed")
        await _idle(stop, settings.HOUSEKEEPING_INTERVAL_SECONDS)


async def run_forever(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, stop: asyncio.Event) -> None:
    logger.info("worker started", extra={"extra_fields": {"pid": os.getpid()}})
    await asyncio.gather(
        run_outbox_relay(sessionmaker, redis, settings, stop),
        run_inbound_consumer(sessionmaker, redis, settings, stop),
        run_index_loop(sessionmaker, settings, stop),
        run_escalation_loop(sessionmaker, settings, stop),
        run_housekeeping(sessionmaker, settings, stop),
    )
    logger.info("worker stopped")
