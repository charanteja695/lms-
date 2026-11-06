"""Recomputing DailyRollup from EventFact (docs/PRODUCT.md §5.9 "Aggregation"): always safe to re-run, and
correct across a mix of organisations and dimension values."""

from sqlalchemy import select

from app.aggregations.rollup import recompute_days
from app.core.time import utcnow
from app.models.fact import DailyRollup
from app.services.ingest_service import ingest

ORG_A, ORG_B = 1755000000121001, 1755000000121002


async def _ingest(db, event_id: str, event_type: str, payload: dict) -> None:
    await ingest(db, event_id=event_id, event_type=event_type, occurred_time=utcnow(), payload=payload)


async def test_rollup_sums_counts_and_measures_grouped_by_org_and_dim(sessionmaker):
    async with sessionmaker() as db:
        await _ingest(db, "1", "attempt.finalized", {"organization_id": str(ORG_A), "result": "passed", "percent": 80.0})
        await _ingest(db, "2", "attempt.finalized", {"organization_id": str(ORG_A), "result": "passed", "percent": 90.0})
        await _ingest(db, "3", "attempt.finalized", {"organization_id": str(ORG_A), "result": "failed", "percent": 40.0})
        await _ingest(db, "4", "attempt.finalized", {"organization_id": str(ORG_B), "result": "passed", "percent": 70.0})
        await db.commit()
        rows = await recompute_days(db, [utcnow().date()])
        assert rows == 3  # (ORG_A, passed), (ORG_A, failed), (ORG_B, passed)

    async with sessionmaker() as db:
        a_passed = (await db.execute(select(DailyRollup).where(DailyRollup.organization_id == ORG_A, DailyRollup.dim_value == "passed"))).scalar_one()
        assert a_passed.count == 2 and a_passed.sum_a == 170.0


async def test_recomputing_a_day_replaces_it_rather_than_accumulating(sessionmaker):
    async with sessionmaker() as db:
        await _ingest(db, "1", "certificate.issued", {"organization_id": str(ORG_A)})
        await db.commit()
        await recompute_days(db, [utcnow().date()])
        await recompute_days(db, [utcnow().date()])  # re-run: must not double the count
        row = (await db.execute(select(DailyRollup).where(DailyRollup.event_type == "certificate.issued"))).scalar_one()
        assert row.count == 1
