"""The job queue. Runs and submissions are rows: a worker *claims* due rows (``FOR UPDATE SKIP LOCKED``, so
workers never fight over one), pushing ``available_at`` out by a lease before it starts. A worker that dies
mid-job simply lets the lease lapse and the row is claimed again — nothing is lost, and nothing is held
locked while code runs. Lanes are served highest priority first, so an exam never waits behind practice
(docs/PRODUCT.md §5.2: exam > practice).

A database queue is deliberate for now: it is transactional with the rows it serves and needs nothing else
running. At sustained thousands of jobs per second the claim step is the part to move to a stream/queue
service, without touching the judge (see the README's "Scaling").
"""

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.time import utcnow
from app.domain.enums import JobStatus, Priority
from app.models.run import Run
from app.models.submission import Submission

Job = Run | Submission
JobModel = type[Run] | type[Submission]

_LANES = (Priority.EXAM, Priority.SUBMISSION, Priority.PRACTICE)


class QueueService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def claim(self, model: JobModel, limit: int) -> list[Job]:
        """Take up to ``limit`` due jobs, highest lane first. Each claim counts an attempt and starts a lease."""
        table: Any = model  # both models share the queue columns; mypy cannot see that through a union of classes
        now = utcnow()
        lease_until = now + timedelta(seconds=self.settings.JOB_LEASE_SECONDS)
        claimed: list[Job] = []
        for lane in _LANES:
            remaining = limit - len(claimed)
            if remaining <= 0:
                break
            rows = (
                await self.db.execute(
                    select(table)
                    .where(table.status != JobStatus.COMPLETED, table.priority == lane, table.available_at <= now)
                    .order_by(table.available_at)
                    .limit(remaining)
                    .with_for_update(skip_locked=True)
                )
            ).scalars()
            for job in rows:
                job.status = JobStatus.RUNNING
                job.attempts += 1
                job.available_at = lease_until
                claimed.append(job)
        await self.db.commit()
        return claimed

    async def depth(self, model: JobModel) -> dict[int, int]:
        """Waiting jobs per lane, for monitoring."""
        rows = (
            await self.db.execute(
                select(model.priority, func.count()).where(model.status != JobStatus.COMPLETED).group_by(model.priority)
            )
        ).all()
        return {int(priority): int(count) for priority, count in rows}
