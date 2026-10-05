"""Background worker: relays this service's outbox, consumes ``lms:events``, and does everything that must happen
without a request: flushing buffered answers, submitting attempts that ran out of time, grading, sending coding
answers to be judged, releasing results and refreshing question statistics.

Run one or more instances with ``python -m app.worker``; they share the work safely (rows are claimed with
``FOR UPDATE SKIP LOCKED`` and a lease; buffered attempts are claimed atomically in Redis).
"""

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable

from lms_common.events import StreamConsumer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.code_execution import CodeExecutionClient
from app.core.config import Settings
from app.events.consumers.router import dispatch
from app.events.publisher import RedisStreamPublisher, relay_outbox
from app.services.answer_buffer import AnswerBuffer
from app.services.answer_store import AnswerStore
from app.services.attempt_service import AttemptService
from app.services.coding_service import dispatch_due, reconcile_due
from app.services.grading_service import GradingService
from app.services.idempotency_service import IdempotencyService
from app.services.processed_event_service import ProcessedEventService
from app.services.result_service import ResultService
from app.services.stats_service import process_dirty

logger = logging.getLogger("app.worker")


async def _idle(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except TimeoutError:
        pass


async def _loop(name: str, step: Callable[[], Awaitable[int]], stop: asyncio.Event, idle_seconds: float) -> None:
    """Run ``step`` until stopped, sleeping only when it found nothing to do; an exception is logged, never fatal."""
    while not stop.is_set():
        try:
            worked = await step()
        except Exception:
            logger.exception("%s iteration failed", name)
            worked = 0
        if not worked:
            await _idle(stop, idle_seconds)


async def run_outbox_relay(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, stop: asyncio.Event) -> None:
    publisher = RedisStreamPublisher(redis, settings)
    await _loop("outbox relay", lambda: relay_outbox(sessionmaker, publisher, batch_size=settings.OUTBOX_BATCH_SIZE), stop, settings.WORKER_POLL_SECONDS)


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


async def flush_answers(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings) -> int:
    """Move buffered answers of dirty attempts into the database, a batch of attempts at a time."""
    buffer = AnswerBuffer(redis, settings)
    flushed = 0
    for public_id in await buffer.take_dirty(settings.ANSWER_FLUSH_BATCH_ATTEMPTS):
        try:
            async with sessionmaker() as db:
                attempt = await AttemptService(db, settings, redis).get(public_id)
                await AnswerStore(db).flush(attempt, buffer)
            flushed += 1
        except Exception:
            logger.exception("answer flush failed for attempt %s", public_id)
            await buffer.requeue(public_id)
    return flushed


async def sweep_attempts(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings) -> int:
    async with sessionmaker() as db:
        submitted = await AttemptService(db, settings, redis).sweep_timeouts(settings.TIMEOUT_SWEEP_BATCH)
    async with sessionmaker() as db:
        await AttemptService(db, settings, redis).drop_stale_prepared()
    return submitted


async def grade_submitted(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings) -> int:
    async with sessionmaker() as db:
        claimed = await GradingService(db, settings, redis).claim(settings.JOB_BATCH_SIZE)
    semaphore = asyncio.Semaphore(settings.WORKER_CONCURRENCY)

    async def one(public_id: int) -> None:
        async with semaphore:
            try:
                async with sessionmaker() as db:
                    await GradingService(db, settings, redis).grade_attempt(public_id)
            except Exception:
                logger.exception("grading failed for attempt %s; it will be retried when its lease lapses", public_id)

    await asyncio.gather(*(one(public_id) for public_id in claimed))
    return len(claimed)


async def release_results(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings) -> int:
    async with sessionmaker() as db:
        return await ResultService(db, settings, redis).release_due(settings.JOB_BATCH_SIZE)


async def run_housekeeping(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            async with sessionmaker() as db:
                events = await ProcessedEventService(db).prune(retention_days=settings.PROCESSED_EVENTS_RETENTION_DAYS)
            async with sessionmaker() as db:
                keys = await IdempotencyService(db).prune(retention_hours=settings.IDEMPOTENCY_RETENTION_HOURS)
            if events or keys:
                logger.info("housekeeping", extra={"extra_fields": {"processed_events_pruned": events, "idempotency_keys_pruned": keys}})
        except Exception:
            logger.exception("housekeeping failed")
        await _idle(stop, settings.HOUSEKEEPING_INTERVAL_SECONDS)


async def run_forever(sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, stop: asyncio.Event) -> None:
    client = CodeExecutionClient(settings)
    logger.info("worker started", extra={"extra_fields": {"pid": os.getpid()}})
    poll, flush = settings.WORKER_POLL_SECONDS, settings.ANSWER_FLUSH_INTERVAL_SECONDS
    await asyncio.gather(
        run_outbox_relay(sessionmaker, redis, settings, stop),
        run_inbound_consumer(sessionmaker, redis, settings, stop),
        _loop("answer flush", lambda: flush_answers(sessionmaker, redis, settings), stop, flush),
        _loop("timeout sweep", lambda: sweep_attempts(sessionmaker, redis, settings), stop, poll * 5),
        _loop("grading", lambda: grade_submitted(sessionmaker, redis, settings), stop, poll),
        _loop("code dispatch", lambda: dispatch_due(sessionmaker, client, settings, redis), stop, poll),
        _loop("code reconcile", lambda: reconcile_due(sessionmaker, client, settings, redis), stop, poll * 5),
        _loop("result release", lambda: release_results(sessionmaker, redis, settings), stop, poll * 5),
        _loop("statistics", lambda: process_dirty(sessionmaker, redis, settings), stop, settings.STATS_INTERVAL_SECONDS),
        run_housekeeping(sessionmaker, settings, stop),
    )
    logger.info("worker stopped")
