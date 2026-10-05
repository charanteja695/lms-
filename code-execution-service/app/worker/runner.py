"""Background worker: relays this service's outbox, executes queued runs, judges queued submissions and
trims old data. Run one or more instances with ``python -m app.worker``; they share the queue safely
(rows are claimed with SKIP LOCKED and a lease, see app/services/queue_service.py).

Every execution in flight on this process shares one limit, WORKER_CONCURRENCY: it is the knob that sizes
a worker to its machine (or to the Judge0 pool behind it).
"""

import asyncio
import logging
import os
import uuid
from collections.abc import Awaitable, Callable

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.crypto import SecretCipher
from app.engines.factory import RoutingEngine, build_engine
from app.events.publisher import RedisStreamPublisher, relay_outbox
from app.models.run import Run
from app.models.submission import Submission
from app.services.housekeeping import Housekeeping
from app.services.judge_service import JudgeService
from app.services.queue_service import QueueService

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


async def run_job_loop(
    name: str,
    model: type[Run] | type[Submission],
    process: Callable[[uuid.UUID], Awaitable[None]],
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    slots: asyncio.Semaphore,
    stop: asyncio.Event,
) -> None:
    """Keep this worker's execution slots full. One claimer takes due jobs and hands them to consumers through a
    bounded queue *as slots free up* — not in lock-step batches, where one slow job (a 10 s run among 100 ms ones)
    would leave every other slot idle until it finished. A job that raises is logged and left leased: it is
    retried when the lease lapses, and given up after JOB_MAX_ATTEMPTS."""
    capacity = settings.WORKER_CONCURRENCY
    # Claiming is a transaction: do it for a handful of jobs at once rather than one per freed slot.
    min_claim = max(1, min(settings.JOB_BATCH_SIZE, capacity) // 4)
    ready: asyncio.Queue[uuid.UUID] = asyncio.Queue()
    busy = 0
    freed = asyncio.Event()

    async def consumer() -> None:
        nonlocal busy
        while True:
            job_id = await ready.get()
            busy += 1
            try:
                async with slots:
                    await process(job_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("%s failed", name, extra={"extra_fields": {"job": str(job_id)}})
            finally:
                busy -= 1
                ready.task_done()
                freed.set()

    consumers = [asyncio.create_task(consumer()) for _ in range(capacity)]
    try:
        while not stop.is_set():
            room = capacity - ready.qsize() - busy
            if room < min_claim:  # (with nothing in flight, room is the full capacity, so this never idles a free worker)
                freed.clear()
                try:  # wait for a slot to free, or for the poll interval (a lapsed lease may have made a job due)
                    await asyncio.wait_for(freed.wait(), timeout=settings.WORKER_POLL_SECONDS)
                except TimeoutError:
                    pass
                continue
            try:
                async with sessionmaker() as db:
                    jobs = await QueueService(db, settings).claim(model, min(room, settings.JOB_BATCH_SIZE))
                    ids = [job.id for job in jobs]
            except Exception:
                logger.exception("%s claim failed", name)
                ids = []
            for job_id in ids:
                ready.put_nowait(job_id)
            if not ids:
                await _idle(stop, settings.WORKER_POLL_SECONDS)
        await ready.join()  # claimed jobs are finished, not abandoned to their leases
    finally:
        for task in consumers:
            task.cancel()
        await asyncio.gather(*consumers, return_exceptions=True)


async def run_housekeeping(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            async with sessionmaker() as db:
                runs = await Housekeeping(db, settings).prune_runs()
            async with sessionmaker() as db:
                keys = await Housekeeping(db, settings).prune_idempotency_keys()
            if runs or keys:
                logger.info("housekeeping", extra={"extra_fields": {"runs_pruned": runs, "idempotency_keys_pruned": keys}})
        except Exception:
            logger.exception("housekeeping failed")
        await _idle(stop, settings.HOUSEKEEPING_INTERVAL_SECONDS)


async def run_forever(
    sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, stop: asyncio.Event
) -> None:
    engine: RoutingEngine = build_engine(settings)
    judge = JudgeService(sessionmaker, engine, settings, SecretCipher.from_settings(settings))
    slots = asyncio.Semaphore(settings.WORKER_CONCURRENCY)
    logger.info(
        "worker started",
        extra={"extra_fields": {"pid": os.getpid(), "engine": settings.EXECUTION_ENGINE, "concurrency": settings.WORKER_CONCURRENCY}},
    )
    try:
        await asyncio.gather(
            run_outbox_relay(sessionmaker, redis, settings, stop),
            run_job_loop("submission", Submission, judge.process_submission, sessionmaker, settings, slots, stop),
            run_job_loop("run", Run, judge.process_run, sessionmaker, settings, slots, stop),
            run_housekeeping(sessionmaker, settings, stop),
        )
    finally:
        await engine.aclose()
    logger.info("worker stopped")
