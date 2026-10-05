"""The one query every dashboard is built from: totals per (event type, dimension value) over a date range,
optionally scoped to one organisation or one employer. Reads `DailyRollup` only — the worker's periodic tick
(``ROLLUP_INTERVAL_SECONDS``, default 5 minutes) keeps the trailing days close enough to live for a dashboard;
see the README for what "near-real-time" means here."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models.fact import DailyRollup


@dataclass(frozen=True, slots=True)
class Totals:
    event_type: str
    dim_value: str
    count: int
    sum_a: float
    sum_b: float


def date_range(days: int) -> tuple[date, date]:
    until = utcnow().date()
    return until - timedelta(days=max(days - 1, 0)), until


async def rollup_totals(
    db: AsyncSession, event_types: Sequence[str], *, organization_id: int | None = None, employer_id: int | None = None, since: date, until: date
) -> list[Totals]:
    stmt = (
        select(DailyRollup.event_type, DailyRollup.dim_value, func.coalesce(func.sum(DailyRollup.count), 0), func.coalesce(func.sum(DailyRollup.sum_a), 0.0), func.coalesce(func.sum(DailyRollup.sum_b), 0.0))
        .where(DailyRollup.event_type.in_(event_types), DailyRollup.day >= since, DailyRollup.day <= until)
        .group_by(DailyRollup.event_type, DailyRollup.dim_value)
    )
    if organization_id is not None:
        stmt = stmt.where(DailyRollup.organization_id == organization_id)
    if employer_id is not None:
        stmt = stmt.where(DailyRollup.employer_id == employer_id)
    rows = (await db.execute(stmt)).all()
    return [Totals(event_type=r[0], dim_value=r[1], count=int(r[2]), sum_a=float(r[3]), sum_b=float(r[4])) for r in rows]


def total(rows: list[Totals], event_type: str) -> int:
    return sum(r.count for r in rows if r.event_type == event_type)


def by_dim(rows: list[Totals], event_type: str) -> dict[str, int]:
    return {r.dim_value: r.count for r in rows if r.event_type == event_type and r.dim_value}


def sum_a_total(rows: list[Totals], event_type: str) -> float:
    return sum(r.sum_a for r in rows if r.event_type == event_type)


def sum_b_total(rows: list[Totals], event_type: str) -> float:
    return sum(r.sum_b for r in rows if r.event_type == event_type)


def avg_a(rows: list[Totals], event_type: str) -> float | None:
    matching = [r for r in rows if r.event_type == event_type]
    count = sum(r.count for r in matching)
    return round(sum(r.sum_a for r in matching) / count, 2) if count else None
