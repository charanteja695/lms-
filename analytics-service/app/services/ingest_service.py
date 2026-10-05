"""Turn one inbound event into an `EventFact` row (docs/PRODUCT.md §5.9). Idempotency is the router's job
(`ProcessedEventService`, same as every consumer here) — this only extracts and writes."""

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.ingest.extract import REGISTRY, Extract
from app.models.fact import NONE_DIM, NONE_ORG, EnrollmentRef, EventFact


def _int(value: Any) -> int:
    try:
        return int(str(value)) if value not in (None, "") else NONE_ORG
    except ValueError:
        return NONE_ORG


def _str(value: Any) -> str:
    return str(value)[:60] if value not in (None, "") else NONE_DIM


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def _resolve_organization(db: AsyncSession, spec: Extract, payload: dict[str, Any]) -> int:
    if spec.org_field:
        return _int(payload.get(spec.org_field))
    if spec.via_enrollment:
        enrollment_id = _int(payload.get("enrollment_id"))
        if enrollment_id != NONE_ORG:
            ref = await db.get(EnrollmentRef, enrollment_id)
            if ref is not None:
                return ref.organization_id
    return NONE_ORG


async def ingest(db: AsyncSession, *, event_id: str, event_type: str, occurred_time: datetime, payload: dict[str, Any]) -> None:
    """Update the `EnrollmentRef` read-model (if this is `enrollment.created`) and, if this event type is one
    this service tracks, write its `EventFact`. Both in the caller's transaction."""
    if event_type == "enrollment.created":
        enrollment_id = _int(payload.get("enrollment_id"))
        if enrollment_id != NONE_ORG and await db.get(EnrollmentRef, enrollment_id) is None:
            db.add(EnrollmentRef(enrollment_id=enrollment_id, organization_id=_int(payload.get("organization_id")), student_user_id=_int(payload.get("student_user_id"))))

    spec = REGISTRY.get(event_type)
    if spec is None:
        return  # not one of the events this service's dashboards use

    measure_b = spec.value_b_compute(payload) if spec.value_b_compute else _float(payload.get(spec.value_b_field)) if spec.value_b_field else None
    db.add(
        EventFact(
            event_id=event_id, event_type=event_type, occurred_at=occurred_time, organization_id=await _resolve_organization(db, spec, payload),
            employer_id=_int(payload.get(spec.employer_field)) if spec.employer_field else NONE_ORG, dim_key=spec.dim_key or NONE_DIM,
            dim_value=_str(payload.get(spec.dim_field)) if spec.dim_field else NONE_DIM, measure_a=_float(payload.get(spec.value_a_field)) if spec.value_a_field else None,
            measure_b=measure_b, payload=payload, ingested_at=utcnow(),
        )
    )
