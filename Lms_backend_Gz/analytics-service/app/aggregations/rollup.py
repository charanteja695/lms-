"""Recompute `DailyRollup` for a set of days from `EventFact` (docs/PRODUCT.md §5.9 "Aggregation"): sum
`EventFact` for those days and upsert the result. An upsert, not delete-then-insert, so two workers
recomputing the same day at once never race — the unique index on `DailyRollup`'s key columns serialises the
two writes, and both compute the same total from the same committed `EventFact` rows regardless of which
commits last. Always safe to re-run — a rollup is a cache of `EventFact`, never the source of truth."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fact import DailyRollup, EventFact

_KEY_COLUMNS = ["event_type", "organization_id", "employer_id", "dim_key", "dim_value", "day"]


async def recompute_days(db: AsyncSession, days: list[date]) -> int:
    if not days:
        return 0
    day_col = func.date(EventFact.occurred_at)
    rows = (
        await db.execute(
            select(
                EventFact.event_type, EventFact.organization_id, EventFact.employer_id, EventFact.dim_key, EventFact.dim_value, day_col.label("day"),
                func.count().label("count"), func.coalesce(func.sum(EventFact.measure_a), 0.0).label("sum_a"), func.coalesce(func.sum(EventFact.measure_b), 0.0).label("sum_b"),
            )
            .where(day_col.in_(days))
            .group_by(EventFact.event_type, EventFact.organization_id, EventFact.employer_id, EventFact.dim_key, EventFact.dim_value, day_col)
        )
    ).all()
    present: set[tuple[str, int, int, str, str, str]] = set()
    values = []
    for row in rows:
        day = row.day if isinstance(row.day, date) else date.fromisoformat(str(row.day))
        present.add((row.event_type, row.organization_id, row.employer_id, row.dim_key, row.dim_value, day.isoformat()))
        values.append({"event_type": row.event_type, "organization_id": row.organization_id, "employer_id": row.employer_id, "dim_key": row.dim_key, "dim_value": row.dim_value, "day": day, "count": row.count, "sum_a": row.sum_a, "sum_b": row.sum_b})
    if values:
        insert = postgresql.insert if db.bind is not None and db.bind.dialect.name == "postgresql" else sqlite.insert
        stmt = insert(DailyRollup).values(values)
        stmt = stmt.on_conflict_do_update(index_elements=_KEY_COLUMNS, set_={"count": stmt.excluded.count, "sum_a": stmt.excluded.sum_a, "sum_b": stmt.excluded.sum_b})
        await db.execute(stmt)
    # A key that had rows before but none now (e.g. an EventFact was pruned) would otherwise linger forever.
    stale = await db.execute(select(DailyRollup).where(DailyRollup.day.in_(days)))
    for existing in stale.scalars():
        key = (existing.event_type, existing.organization_id, existing.employer_id, existing.dim_key, existing.dim_value, existing.day.isoformat())
        if key not in present:
            await db.delete(existing)
    await db.commit()
    return len(rows)
