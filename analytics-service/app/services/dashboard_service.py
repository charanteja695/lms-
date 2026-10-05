"""The seven dashboards (docs/PRODUCT.md §5.9), each a shape built from `rollup_totals` — never a raw list of
rows, always a small number that traces back to real `EventFact` rows (see app/ingest/extract.py). Every
function takes ``since``/``until`` (see `app.services.rollup_query.date_range`) and returns a plain dict, so
the same function serves both a live dashboard read and a scheduled report run (`report_service.py`)."""

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rollup_query import avg_a, by_dim, rollup_totals, sum_a_total, sum_b_total, total


def _rate(passed: int, failed: int) -> float | None:
    denom = passed + failed
    return round(passed / denom, 3) if denom else None


async def institution(db: AsyncSession, *, organization_id: int, since: date, until: date) -> dict[str, Any]:
    """An institution's own funnel: enrolment, completion, exam results, integrity, certificates, placement."""
    types = ["enrollment.created", "topic.completed", "module.completed", "course.eligible_for_final", "attempt.finalized", "certificate.issued", "certificate.revoked", "candidate.placed"]
    rows = await rollup_totals(db, types, organization_id=organization_id, since=since, until=until)
    results = by_dim(rows, "attempt.finalized")
    return {
        "organization_id": str(organization_id), "since": since.isoformat(), "until": until.isoformat(),
        "enrollments": total(rows, "enrollment.created"), "topic_completions": total(rows, "topic.completed"), "module_completions": total(rows, "module.completed"),
        "eligible_for_final": total(rows, "course.eligible_for_final"), "tests_finalized": total(rows, "attempt.finalized"), "tests_passed": results.get("passed", 0),
        "tests_failed": results.get("failed", 0), "tests_invalidated": results.get("invalidated", 0), "test_pass_rate": _rate(results.get("passed", 0), results.get("failed", 0)),
        "certificates_issued": total(rows, "certificate.issued"), "certificates_revoked": total(rows, "certificate.revoked"), "students_placed": total(rows, "candidate.placed"),
    }


async def content(db: AsyncSession, *, since: date, until: date) -> dict[str, Any]:
    """Platform-wide learning funnel. No per-course breakdown: the events this service ingests carry a topic or
    module id, not a course id or title — that lookup belongs to catalog-service, which this service never calls
    synchronously (see the README's "Known limits")."""
    types = ["enrollment.created", "topic.completed", "module.completed", "course.eligible_for_final", "course.passed", "course.failed", "course.pass_revoked"]
    rows = await rollup_totals(db, types, since=since, until=until)
    passed, failed = total(rows, "course.passed"), total(rows, "course.failed")
    return {
        "since": since.isoformat(), "until": until.isoformat(), "enrollments": total(rows, "enrollment.created"), "topic_completions": total(rows, "topic.completed"),
        "module_completions": total(rows, "module.completed"), "eligible_for_final": total(rows, "course.eligible_for_final"), "courses_passed": passed, "courses_failed": failed,
        "pass_revoked": total(rows, "course.pass_revoked"), "course_pass_rate": _rate(passed, failed), "average_pass_percent": avg_a(rows, "course.passed"),
    }


async def exam_integrity(db: AsyncSession, *, since: date, until: date) -> dict[str, Any]:
    """Platform-wide (integrity events carry no organisation — see app/ingest/extract.py)."""
    types = ["attempt.finalized", "integrity.flagged", "integrity.decided"]
    rows = await rollup_totals(db, types, since=since, until=until)
    return {
        "since": since.isoformat(), "until": until.isoformat(), "attempts_finalized": total(rows, "attempt.finalized"), "results": by_dim(rows, "attempt.finalized"),
        "average_percent": avg_a(rows, "attempt.finalized"), "integrity_flags": total(rows, "integrity.flagged"), "flags_by_stage": by_dim(rows, "integrity.flagged"),
        "integrity_decisions": total(rows, "integrity.decided"), "decisions_by_outcome": by_dim(rows, "integrity.decided"),
    }


async def support(db: AsyncSession, *, organization_id: int | None, since: date, until: date) -> dict[str, Any]:
    types = ["ticket.created", "ticket.status_changed", "ticket.sla_breached", "ticket.csat_submitted"]
    rows = await rollup_totals(db, types, organization_id=organization_id, since=since, until=until)
    return {
        "organization_id": str(organization_id) if organization_id else None, "since": since.isoformat(), "until": until.isoformat(), "tickets_created": total(rows, "ticket.created"),
        "by_category": by_dim(rows, "ticket.created"), "status_changes": total(rows, "ticket.status_changed"), "by_status": by_dim(rows, "ticket.status_changed"),
        "sla_breaches": total(rows, "ticket.sla_breached"), "breaches_by_kind": by_dim(rows, "ticket.sla_breached"), "csat_responses": total(rows, "ticket.csat_submitted"),
        "average_csat": avg_a(rows, "ticket.csat_submitted"),
    }


async def hiring(db: AsyncSession, *, employer_id: int | None, organization_id: int | None, since: date, until: date) -> dict[str, Any]:
    """Platform-wide (both ``employer_id`` and ``organization_id`` left unset), one employer's own jobs
    (``employer_id`` set — recruiters and admins), or one institution's own students' outcomes
    (``organization_id`` set — the institution overview dashboard also draws its placement count from here)."""
    types = ["application.stage_changed", "candidate.placed", "offer.extended", "offer.accepted", "offer.declined", "offer.expired", "interview.completed", "interview.reviewed"]
    rows = await rollup_totals(db, types, organization_id=organization_id, employer_id=employer_id, since=since, until=until)
    return {
        "employer_id": str(employer_id) if employer_id else None, "organization_id": str(organization_id) if organization_id else None, "since": since.isoformat(), "until": until.isoformat(),
        "applications_by_stage": by_dim(rows, "application.stage_changed"), "placements": total(rows, "candidate.placed"), "average_placement_ctc": avg_a(rows, "candidate.placed"),
        "offers_extended": total(rows, "offer.extended"), "offers_accepted": total(rows, "offer.accepted"), "offers_declined": total(rows, "offer.declined"), "offers_expired": total(rows, "offer.expired"),
        "interviews_completed": total(rows, "interview.completed"), "ai_recommendations": by_dim(rows, "interview.completed"), "human_overrides": by_dim(rows, "interview.reviewed"),
    }


async def ai_usage(db: AsyncSession, *, organization_id: int | None, since: date, until: date) -> dict[str, Any]:
    rows = await rollup_totals(db, ["ai.usage"], organization_id=organization_id, since=since, until=until)
    return {
        "organization_id": str(organization_id) if organization_id else None, "since": since.isoformat(), "until": until.isoformat(), "calls": total(rows, "ai.usage"),
        "by_capability": by_dim(rows, "ai.usage"), "total_cost_cents": sum_a_total(rows, "ai.usage"), "total_tokens": sum_b_total(rows, "ai.usage"),
    }


async def billing(db: AsyncSession, *, organization_id: int | None, since: date, until: date) -> dict[str, Any]:
    """From billing-service's events (docs/PRODUCT.md §5.10). Amounts are paise, as billing emits them. ``plan.*`` events
    belong to the employer (``employer_id``), so an ``organization_id`` filter only ever shows an institution's invoices."""
    types = ["invoice.issued", "invoice.paid", "invoice.overdue", "invoice.voided", "credit_note.issued", "plan.activated", "plan.expired"]
    rows = await rollup_totals(db, types, organization_id=organization_id, since=since, until=until)
    return {
        "organization_id": str(organization_id) if organization_id else None, "since": since.isoformat(), "until": until.isoformat(), "invoices_issued": total(rows, "invoice.issued"),
        "invoiced_amount": sum_a_total(rows, "invoice.issued"), "invoices_paid": total(rows, "invoice.paid"), "paid_amount": sum_a_total(rows, "invoice.paid"),
        "invoices_overdue": total(rows, "invoice.overdue"), "overdue_amount": sum_a_total(rows, "invoice.overdue"), "invoices_voided": total(rows, "invoice.voided"),
        "credit_notes": total(rows, "credit_note.issued"), "credit_amount": sum_a_total(rows, "credit_note.issued"), "plans_activated": total(rows, "plan.activated"), "plans_expired": total(rows, "plan.expired"),
    }
