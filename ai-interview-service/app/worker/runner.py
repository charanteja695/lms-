"""Background worker: relays this service's outbox, consumes ``lms:events``, runs the durable work (evaluating finished interviews, inviting candidates
the pipeline sent), ends interviews whose time ran out and expires invitations nobody used, and prunes finished work. Run one or more instances with
``python -m app.worker`` (work is claimed with SKIP LOCKED and a lease, so instances never do the same item twice)."""

import asyncio
import logging
import os
from datetime import timedelta

from lms_common.events import StreamConsumer
from redis.asyncio import Redis
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.gateway import GatewayClient
from app.core.config import Settings
from app.core.time import utcnow
from app.domain.enums import WorkStatus
from app.events.consumers.router import dispatch
from app.events.publisher import RedisStreamPublisher, relay_outbox
from app.models.work import WorkItem
from app.services.interview_service import InterviewService
from app.services.processed_event_service import ProcessedEventService
from app.worker.work import run_due

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


async def run_work_loop(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, stop: asyncio.Event) -> None:
    gateway = GatewayClient(settings)
    while not stop.is_set():
        try:
            worked = await run_due(sessionmaker, settings, gateway)
        except Exception:
            logger.exception("work loop iteration failed")
            worked = 0
        if not worked:
            await _idle(stop, settings.WORKER_POLL_SECONDS)


async def sweep_once(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings) -> tuple[int, int]:
    """End interviews whose time ran out and expire unused invitations. Returns ``(interviews ended, invitations expired)``."""
    async with sessionmaker() as db:
        return await InterviewService(db, settings).close_stale()


async def run_sweeps(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            ended, expired = await sweep_once(sessionmaker, settings)
            if ended or expired:
                logger.info("sweep", extra={"extra_fields": {"interviews_ended": ended, "invitations_expired": expired}})
        except Exception:
            logger.exception("sweep failed")
        await _idle(stop, settings.WORKER_POLL_SECONDS * 10)


async def housekeeping_once(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings) -> tuple[int, int]:
    """Prune de-duplication records and finished work items (failed ones are kept for staff to see)."""
    async with sessionmaker() as db:
        pruned = await ProcessedEventService(db).prune(retention_days=settings.PROCESSED_EVENTS_RETENTION_DAYS)
    async with sessionmaker() as db:
        result = await db.execute(delete(WorkItem).where(WorkItem.status == WorkStatus.DONE, WorkItem.done_at < utcnow() - timedelta(days=settings.WORK_RETENTION_DAYS)))
        await db.commit()
        return pruned, int(getattr(result, "rowcount", 0) or 0)


async def run_housekeeping(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            pruned, work = await housekeeping_once(sessionmaker, settings)
            if pruned or work:
                logger.info("housekeeping", extra={"extra_fields": {"pruned_processed_events": pruned, "pruned_work_items": work}})
        except Exception:
            logger.exception("housekeeping failed")
        await _idle(stop, settings.HOUSEKEEPING_INTERVAL_SECONDS)


async def run_forever(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, stop: asyncio.Event) -> None:
    logger.info("worker started", extra={"extra_fields": {"pid": os.getpid()}})
    await asyncio.gather(
        run_outbox_relay(sessionmaker, redis, settings, stop),
        run_inbound_consumer(sessionmaker, redis, settings, stop),
        run_work_loop(sessionmaker, settings, stop),
        run_sweeps(sessionmaker, settings, stop),
        run_housekeeping(sessionmaker, settings, stop),
    )
    logger.info("worker stopped")
