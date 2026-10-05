"""The durable work queue: enqueue here, in the same transaction as the change that needs the work; the worker claims items with a lease
(``FOR UPDATE SKIP LOCKED``), runs them, and retries failures with exponential backoff (see app/worker/runner.py)."""

from datetime import timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.time import utcnow
from app.domain.enums import WorkKind, WorkStatus
from app.models.work import WorkItem


async def enqueue(db: AsyncSession, kind: WorkKind, ref_id: int, payload: dict[str, Any] | None = None, *, dedupe: bool = True) -> WorkItem | None:
    """Add work. With ``dedupe`` a pending item for the same kind and subject is reused (the work reads the latest state when it runs)."""
    if dedupe:
        existing = (
            await db.execute(select(WorkItem).where(WorkItem.kind == kind, WorkItem.ref_id == ref_id, WorkItem.status == WorkStatus.PENDING, WorkItem.leased_until.is_(None)))
        ).scalar_one_or_none()
        if existing is not None:
            return None
    item = WorkItem(kind=kind, ref_id=ref_id, payload=payload or {}, status=WorkStatus.PENDING, attempts=0, run_after=utcnow())
    db.add(item)
    await db.flush()
    return item


async def claim(db: AsyncSession, settings: Settings, *, kinds: tuple[WorkKind, ...] | None = None, limit: int | None = None) -> list[WorkItem]:
    """Lease due items. A worker that dies leaves its lease to expire, after which another takes the item over."""
    now = utcnow()
    stmt = (
        select(WorkItem)
        .where(WorkItem.status == WorkStatus.PENDING, WorkItem.run_after <= now, (WorkItem.leased_until.is_(None)) | (WorkItem.leased_until < now))
        .order_by(WorkItem.run_after, WorkItem.created_at)
        .limit(limit or settings.WORK_BATCH)
        .with_for_update(skip_locked=True)
    )
    if kinds:
        stmt = stmt.where(WorkItem.kind.in_([k.value for k in kinds]))
    items = list((await db.execute(stmt)).scalars())
    for item in items:
        item.leased_until = now + timedelta(seconds=settings.WORK_LEASE_SECONDS)
        item.attempts += 1
    await db.commit()
    return items


async def finish(db: AsyncSession, item_id: Any) -> None:
    await db.execute(update(WorkItem).where(WorkItem.id == item_id).values(status=WorkStatus.DONE, done_at=utcnow(), leased_until=None, last_error=None))
    await db.commit()


async def fail(db: AsyncSession, settings: Settings, item_id: Any, attempts: int, error: str, *, permanent: bool = False) -> None:
    """Retry later with backoff, or give up (``failed``: visible to staff, never silently lost)."""
    if permanent or attempts >= settings.WORK_MAX_ATTEMPTS:
        values: dict[str, Any] = {"status": WorkStatus.FAILED, "leased_until": None, "last_error": error[:300]}
    else:
        values = {"leased_until": None, "last_error": error[:300], "run_after": utcnow() + timedelta(seconds=settings.WORK_BACKOFF_BASE_SECONDS * 2 ** (attempts - 1))}
    await db.execute(update(WorkItem).where(WorkItem.id == item_id).values(**values))
    await db.commit()
