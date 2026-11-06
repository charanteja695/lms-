"""Coding and SQL answers, judged by code-execution-service (docs/PRODUCT.md §5.2, §6.1).

A ``coding_submissions`` row is the durable record that an answer must be judged. Three loops keep it moving, and any
one of them can be lost without losing the answer:

  dispatch   POSTs pending rows to code-execution's exam lane (idempotent by reference; retried with backoff), and
             never holds a database connection across the HTTP call;
  verdicts   the ``submission.judged`` event is matched back to its row by reference;
  reconcile  asks code-execution directly about rows whose event has not arrived, and gives up after a while (the
             answer then goes to a person), so no attempt is ever left waiting forever.
"""

import logging
from datetime import timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.code_execution import CodeExecutionClient, CodeExecutionRejected, CodeExecutionUnavailable, Verdict
from app.core.config import Settings
from app.core.time import utcnow
from app.domain.enums import CodingStatus
from app.models.attempt import CodingSubmission
from app.services.grading_service import GradingService

logger = logging.getLogger(__name__)

_MAX_BACKOFF_SECONDS = 60


async def apply_verdict(db: AsyncSession, settings: Settings, redis: Redis | None, coding: CodingSubmission, verdict: Verdict) -> None:
    """Record code-execution's verdict on the row and regrade the answer. Idempotent."""
    if coding.status == CodingStatus.JUDGED:
        return
    coding.status = CodingStatus.JUDGED
    coding.code_submission_id = verdict.submission_id
    coding.verdict, coding.passed_count, coding.total_count = verdict.verdict, verdict.passed, verdict.total
    coding.score = verdict.score
    coding.flagged = verdict.flagged
    coding.similarity_percent = verdict.similarity_percent
    coding.similar_to_submission_id = verdict.similar_to_submission_id
    coding.judged_at = utcnow()
    await GradingService(db, settings, redis).on_coding_update(coding)


async def handle_judged_event(db: AsyncSession, settings: Settings, redis: Redis | None, payload: dict[str, Any]) -> None:
    """``submission.judged``: only our own submissions (their reference starts with ``attempt:``) matter."""
    reference = payload.get("reference")
    if not isinstance(reference, str) or not reference.startswith("attempt:"):
        return
    coding = (await db.execute(select(CodingSubmission).where(CodingSubmission.reference == reference).with_for_update())).scalar_one_or_none()
    if coding is None:
        logger.warning("submission.judged for an unknown reference %s", reference)
        return
    similar = payload.get("similar_to_submission_id")
    await apply_verdict(
        db,
        settings,
        redis,
        coding,
        Verdict(
            submission_id=int(payload["submission_id"]),
            completed=True,
            verdict=payload.get("verdict"),
            passed=payload.get("passed"),
            total=payload.get("total"),
            score=payload.get("score"),
            flagged=bool(payload.get("flagged", False)),
            similarity_percent=payload.get("similarity_percent"),
            similar_to_submission_id=int(similar) if similar else None,
        ),
    )


async def _give_up(db: AsyncSession, settings: Settings, redis: Redis | None, coding: CodingSubmission, reason: str) -> None:
    coding.status = CodingStatus.FAILED
    coding.last_error = reason[:300]
    await GradingService(db, settings, redis).on_coding_update(coding)


async def dispatch_due(
    sessionmaker: async_sessionmaker[AsyncSession], client: CodeExecutionClient, settings: Settings, redis: Redis | None = None
) -> int:
    """Send pending coding answers to code-execution-service. Returns how many were attempted."""
    now = utcnow()
    async with sessionmaker() as db:
        rows = (
            await db.execute(
                select(CodingSubmission)
                .where(CodingSubmission.status == CodingStatus.PENDING, CodingSubmission.available_at <= now)
                .order_by(CodingSubmission.available_at)
                .limit(settings.CODE_DISPATCH_BATCH)
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()
        jobs = []
        for row in rows:
            row.dispatch_attempts += 1
            row.available_at = now + timedelta(seconds=settings.JOB_LEASE_SECONDS)  # a lease: a crash retries it
            jobs.append((row.id, row.user_id, row.organization_id, row.problem_id, row.language, row.source, row.reference, row.dispatch_attempts))
        await db.commit()

    for row_id, user_id, organization_id, problem_id, language, source, reference, attempts in jobs:
        verdict: Verdict | None = None
        error: str | None = None
        permanent = False
        try:
            verdict = await client.submit(
                user_id=user_id, organization_id=organization_id, problem_id=problem_id, language=language, source=source, reference=reference
            )
        except CodeExecutionRejected as exc:
            error, permanent = str(exc), True
        except CodeExecutionUnavailable as exc:
            error = str(exc)
        async with sessionmaker() as db:
            row = (await db.execute(select(CodingSubmission).where(CodingSubmission.id == row_id).with_for_update())).scalar_one()
            if verdict is not None:
                row.code_submission_id = verdict.submission_id
                row.dispatched_at = utcnow()
                row.last_error = None
                if verdict.completed:
                    await apply_verdict(db, settings, redis, row, verdict)
                else:
                    row.status = CodingStatus.DISPATCHED
                    row.available_at = utcnow() + timedelta(seconds=settings.CODE_RECONCILE_AFTER_SECONDS)
            elif permanent or attempts >= settings.CODE_DISPATCH_MAX_ATTEMPTS:
                await _give_up(db, settings, redis, row, error or "could not be sent for judging")
            else:
                row.last_error = (error or "")[:300]
                row.available_at = utcnow() + timedelta(seconds=min(2**attempts, _MAX_BACKOFF_SECONDS))
            await db.commit()
    return len(jobs)


async def reconcile_due(
    sessionmaker: async_sessionmaker[AsyncSession], client: CodeExecutionClient, settings: Settings, redis: Redis | None = None
) -> int:
    """Ask code-execution about dispatched answers whose verdict event has not arrived (the event stream does not
    redeliver a missed message), and give up on any that take implausibly long."""
    now = utcnow()
    async with sessionmaker() as db:
        rows = (
            await db.execute(
                select(CodingSubmission.id, CodingSubmission.code_submission_id, CodingSubmission.dispatched_at)
                .where(CodingSubmission.status == CodingStatus.DISPATCHED, CodingSubmission.available_at <= now)
                .order_by(CodingSubmission.available_at)
                .limit(settings.CODE_DISPATCH_BATCH)
            )
        ).all()
    checked = 0
    for row_id, submission_id, dispatched_at in rows:
        verdict: Verdict | None = None
        unavailable = False
        try:
            verdict = await client.get(int(submission_id)) if submission_id else None
        except CodeExecutionRejected:
            verdict = None
        except CodeExecutionUnavailable:
            unavailable = True
        async with sessionmaker() as db:
            row = (await db.execute(select(CodingSubmission).where(CodingSubmission.id == row_id).with_for_update())).scalar_one()
            if row.status != CodingStatus.DISPATCHED:
                await db.commit()
                continue
            if verdict is not None and verdict.completed:
                await apply_verdict(db, settings, redis, row, verdict)
            elif dispatched_at is not None and utcnow() - dispatched_at > timedelta(minutes=settings.CODE_GIVE_UP_MINUTES) and not unavailable:
                await _give_up(db, settings, redis, row, "no verdict from code-execution-service in time")
            else:
                row.available_at = utcnow() + timedelta(seconds=settings.CODE_RECONCILE_AFTER_SECONDS)
            await db.commit()
        checked += 1
    return checked
