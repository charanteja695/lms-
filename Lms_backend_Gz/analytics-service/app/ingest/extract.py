"""What is pulled from each event type this service ingests, and why (docs/PRODUCT.md §5.9).

Every field name below is the real, already-shipped payload field of the service that emits it (checked against
its source at the time this was written, not guessed) — see the docstring on each ``Extract`` entry for where.
Three learning-service events (``topic.completed``, ``module.completed``, ``course.eligible_for_final``) and
three assessment-service ones for a course's final result (``course.passed``, ``course.failed``,
``course.pass_revoked``) carry only an ``enrollment_id``, not an organisation, so those are resolved through
``EnrollmentRef`` (built from ``enrollment.created``) instead of read from the payload directly.

Two proctoring-service events (``integrity.flagged``, ``integrity.decided``) carry neither an organisation nor
an enrollment id (only ``user_id``) — this service does not resolve a user to their organisation (that would
need a `UserRef` this service does not build), so those two are ingested platform-wide only (``organization_id``
stays the "none" sentinel). This is a known limit: see the README's "Known limits".
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


def _tokens(payload: dict[str, Any]) -> float | None:
    prompt, completion = payload.get("prompt_tokens"), payload.get("completion_tokens")
    if prompt is None and completion is None:
        return None
    return float(prompt or 0) + float(completion or 0)


@dataclass(frozen=True, slots=True)
class Extract:
    org_field: str | None = None  # payload key holding organization_id, read directly
    employer_field: str | None = None  # payload key holding employer_id, read directly
    via_enrollment: bool = False  # resolve organization_id from EnrollmentRef using payload["enrollment_id"]
    dim_key: str | None = None  # a fixed label for what dim_value means, e.g. "result", "category"
    dim_field: str | None = None  # payload key holding the dimension's value
    value_a_field: str | None = None  # payload key summed into DailyRollup.sum_a
    value_b_field: str | None = None  # payload key summed into DailyRollup.sum_b
    value_b_compute: Callable[[dict[str, Any]], float | None] | None = None  # for a value b built from more than one field


# event_type -> Extract. See each producer's write_event/_emit call for the payload this reads.
REGISTRY: dict[str, Extract] = {
    # learning-service (app/services/enrollment_service.py, progress_service.py)
    "enrollment.created": Extract(org_field="organization_id"),
    "enrollment.removed": Extract(org_field="organization_id"),
    "topic.completed": Extract(via_enrollment=True),
    "module.completed": Extract(via_enrollment=True),
    "course.eligible_for_final": Extract(via_enrollment=True),
    # assessment-service (app/services/result_service.py, attempt_service.py)
    "course.passed": Extract(via_enrollment=True, value_a_field="percent"),
    "course.failed": Extract(via_enrollment=True, value_a_field="percent"),
    "course.pass_revoked": Extract(via_enrollment=True),
    "attempt.finalized": Extract(org_field="organization_id", dim_key="result", dim_field="result", value_a_field="percent"),
    # proctoring-service (app/services/case_service.py) — no organisation in the payload; see the module docstring
    "integrity.flagged": Extract(dim_key="stage", dim_field="stage"),
    "integrity.decided": Extract(dim_key="decision", dim_field="decision"),
    # certificate-service (app/services/issue_service.py)
    "certificate.issued": Extract(org_field="organization_id"),
    "certificate.revoked": Extract(org_field="organization_id"),
    # job-portal-service (app/services/application_service.py, offer_service.py, job_service.py)
    "application.stage_changed": Extract(org_field="organization_id", employer_field="employer_id", dim_key="stage", dim_field="to"),
    "candidate.placed": Extract(org_field="organization_id", employer_field="employer_id", value_a_field="ctc"),
    "job.published": Extract(employer_field="employer_id"),
    "job.closed": Extract(employer_field="employer_id", dim_key="reason", dim_field="reason"),
    "offer.extended": Extract(org_field="organization_id", employer_field="employer_id"),
    "offer.accepted": Extract(org_field="organization_id", employer_field="employer_id"),
    "offer.declined": Extract(org_field="organization_id", employer_field="employer_id"),
    "offer.expired": Extract(org_field="organization_id", employer_field="employer_id"),
    # ai-interview-service (app/services/evaluation_service.py, review_service.py)
    "interview.completed": Extract(employer_field="employer_id", dim_key="recommendation", dim_field="recommendation", value_a_field="score"),
    "interview.evaluated": Extract(dim_key="recommendation", dim_field="recommendation", value_a_field="score"),
    "interview.reviewed": Extract(employer_field="employer_id", dim_key="final_recommendation", dim_field="final_recommendation"),
    # support-service (app/services/ticket_service.py)
    "ticket.created": Extract(org_field="organization_id", dim_key="category", dim_field="category"),
    "ticket.status_changed": Extract(org_field="organization_id", dim_key="status", dim_field="status"),
    "ticket.sla_breached": Extract(org_field="organization_id", dim_key="kind", dim_field="kind"),
    "ticket.csat_submitted": Extract(org_field="organization_id", value_a_field="rating"),
    # ai-gateway (app/services/completion_service.py)
    "ai.usage": Extract(org_field="organization_id", dim_key="capability", dim_field="capability", value_a_field="cost_cents", value_b_compute=_tokens),
    # ai-tutor-service (app/services/escalation_service.py)
    "tutor.escalated": Extract(org_field="organization_id", dim_key="category", dim_field="category"),
    # billing-service (docs/PRODUCT.md §5.10) — not built yet; wired ahead of time, exercised once it emits these
    "invoice.issued": Extract(org_field="organization_id", value_a_field="total_amount"),
    "invoice.paid": Extract(org_field="organization_id", value_a_field="total_amount"),
    "invoice.overdue": Extract(org_field="organization_id", value_a_field="total_amount"),
    "invoice.voided": Extract(org_field="organization_id"),
    "credit_note.issued": Extract(org_field="organization_id", value_a_field="amount"),
    "plan.activated": Extract(employer_field="employer_id", dim_key="tier", dim_field="tier"),
    "plan.expired": Extract(employer_field="employer_id"),
}

# Events whose organisation is only knowable through EnrollmentRef (built from enrollment.created).
ENROLLMENT_EVENTS = frozenset(event_type for event_type, spec in REGISTRY.items() if spec.via_enrollment)
