"""Extraction and ingestion (docs/PRODUCT.md §5.9): what lands in `EventFact` for a real payload shape, and
the `EnrollmentRef` backfill for the three learning events that carry only an ``enrollment_id``."""

from sqlalchemy import select

from app.core.time import utcnow
from app.models.fact import EnrollmentRef, EventFact
from app.services.ingest_service import ingest

ORG, STUDENT = 1755000000120001, 1755000000120101
ENROLLMENT = 1755000000120201


async def _ingest(db, event_type: str, payload: dict) -> None:
    await ingest(db, event_id=f"evt-{event_type}-{payload.get('enrollment_id') or payload.get('user_id') or '1'}", event_type=event_type, occurred_time=utcnow(), payload=payload)
    await db.commit()


async def test_a_direct_organization_id_is_read_straight_from_the_payload(sessionmaker):
    async with sessionmaker() as db:
        await _ingest(db, "certificate.issued", {"certificate_id": "1", "student_user_id": str(STUDENT), "organization_id": str(ORG)})
        fact = (await db.execute(select(EventFact).where(EventFact.event_type == "certificate.issued"))).scalar_one()
        assert fact.organization_id == ORG


async def test_a_null_organization_id_in_the_payload_is_the_none_sentinel(sessionmaker):
    async with sessionmaker() as db:
        await _ingest(db, "certificate.issued", {"certificate_id": "1", "student_user_id": str(STUDENT), "organization_id": None})
        fact = (await db.execute(select(EventFact).where(EventFact.event_type == "certificate.issued"))).scalar_one()
        assert fact.organization_id == 0


async def test_topic_completed_resolves_its_organization_through_enrollment_ref(sessionmaker):
    async with sessionmaker() as db:
        await _ingest(db, "enrollment.created", {"enrollment_id": str(ENROLLMENT), "batch_id": "1", "student_user_id": str(STUDENT), "organization_id": str(ORG)})
        ref = (await db.execute(select(EnrollmentRef).where(EnrollmentRef.enrollment_id == ENROLLMENT))).scalar_one()
        assert ref.organization_id == ORG

        await _ingest(db, "topic.completed", {"enrollment_id": str(ENROLLMENT), "topic_id": "1"})
        fact = (await db.execute(select(EventFact).where(EventFact.event_type == "topic.completed"))).scalar_one()
        assert fact.organization_id == ORG


async def test_an_event_type_this_service_does_not_track_is_not_stored(sessionmaker):
    async with sessionmaker() as db:
        await _ingest(db, "media.ready", {"media_id": "1"})
        count = (await db.execute(select(EventFact))).all()
        assert count == []


async def test_ai_usage_sums_prompt_and_completion_tokens_into_measure_b(sessionmaker):
    async with sessionmaker() as db:
        await _ingest(db, "ai.usage", {"organization_id": str(ORG), "capability": "chat", "cost_cents": 12, "prompt_tokens": 100, "completion_tokens": 50})
        fact = (await db.execute(select(EventFact).where(EventFact.event_type == "ai.usage"))).scalar_one()
        assert fact.measure_a == 12.0 and fact.measure_b == 150.0 and fact.dim_key == "capability" and fact.dim_value == "chat"


async def test_a_dimension_value_that_is_missing_is_the_none_sentinel(sessionmaker):
    async with sessionmaker() as db:
        await _ingest(db, "attempt.finalized", {"organization_id": str(ORG), "percent": 88.0})
        fact = (await db.execute(select(EventFact).where(EventFact.event_type == "attempt.finalized"))).scalar_one()
        assert fact.dim_key == "result" and fact.dim_value == ""


# Payloads copied verbatim from what billing-service really emitted (its outbox, after a full subscription-invoice-payment-credit and a plan purchase).
BILLING_PAYLOADS = {
    "invoice.issued": {"invoice_id": "363007109638278976", "number": "INV/2026-27/000001", "organization_id": "1755000000210001", "kind": "subscription", "status": "issued", "currency": "INR", "occurred_at": "2026-09-28T17:00:39Z", "total_amount": 118000000, "due_date": "2026-10-13"},
    "invoice.paid": {"invoice_id": "363007109638278976", "number": "INV/2026-27/000001", "organization_id": "1755000000210001", "kind": "subscription", "status": "paid", "currency": "INR", "occurred_at": "2026-09-28T17:00:39Z", "total_amount": 118000000},
    "credit_note.issued": {"credit_note_id": "363007110001488927", "number": "CN/2026-27/000001", "invoice_id": "363007109638278976", "organization_id": "1755000000210001", "amount": 1180, "occurred_at": "2026-09-28T17:00:39Z"},
    "plan.activated": {"plan_id": "363007110067689327", "employer_id": "1755000000210011", "organization_id": "1755000000210011", "tier": "growth", "job_posts": 10, "ends_at": "2026-10-28T17:00:39Z", "occurred_at": "2026-09-28T17:00:39Z"},
}


async def test_billing_services_real_events_ingest_with_their_amounts_and_tenants(sessionmaker):
    async with sessionmaker() as db:
        for index, (event_type, payload) in enumerate(BILLING_PAYLOADS.items()):
            await ingest(db, event_id=f"billing-{index}", event_type=event_type, occurred_time=utcnow(), payload=payload)
        await db.commit()
        facts = {f.event_type: f for f in (await db.execute(select(EventFact))).scalars()}
    assert facts["invoice.issued"].organization_id == 1755000000210001 and facts["invoice.issued"].measure_a == 118000000.0
    assert facts["invoice.paid"].measure_a == 118000000.0 and facts["credit_note.issued"].measure_a == 1180.0
    assert facts["plan.activated"].employer_id == 1755000000210011 and facts["plan.activated"].dim_value == "growth"
