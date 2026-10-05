from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.time import utcnow
from app.domain.enums import JobStatus
from app.models.run import Run
from app.services.idempotency_service import IdempotencyService


class Housekeeping:
    """Trims what only needs to live a while: finished runs (a scratch pad, not a record) and idempotency keys.
    Submissions are never deleted here: they are the record of a student's work."""

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def prune_runs(self) -> int:
        result = await self.db.execute(
            delete(Run).where(
                Run.status == JobStatus.COMPLETED,
                Run.created_at < utcnow() - timedelta(days=self.settings.RUNS_RETENTION_DAYS),
            )
        )
        await self.db.commit()
        return int(getattr(result, "rowcount", 0) or 0)

    async def prune_idempotency_keys(self) -> int:
        return await IdempotencyService(self.db).prune(retention_hours=self.settings.IDEMPOTENCY_RETENTION_HOURS)
