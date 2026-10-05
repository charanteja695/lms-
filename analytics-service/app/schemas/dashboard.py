"""Response shapes for the seven dashboards (docs/PRODUCT.md §5.9). Each ``*Out`` mirrors exactly what
app/services/dashboard_service.py returns — the endpoint builds one straight from that dict, wrapped in the
platform's usual `{status, code, message, <resource>}` envelope."""

from lms_common.envelopes import ResponseSchema, SuccessResponse


class InstitutionDashboardOut(ResponseSchema):
    organization_id: str
    since: str
    until: str
    enrollments: int
    topic_completions: int
    module_completions: int
    eligible_for_final: int
    tests_finalized: int
    tests_passed: int
    tests_failed: int
    tests_invalidated: int
    test_pass_rate: float | None
    certificates_issued: int
    certificates_revoked: int
    students_placed: int


class ContentDashboardOut(ResponseSchema):
    since: str
    until: str
    enrollments: int
    topic_completions: int
    module_completions: int
    eligible_for_final: int
    courses_passed: int
    courses_failed: int
    pass_revoked: int
    course_pass_rate: float | None
    average_pass_percent: float | None


class ExamIntegrityDashboardOut(ResponseSchema):
    since: str
    until: str
    attempts_finalized: int
    results: dict[str, int]
    average_percent: float | None
    integrity_flags: int
    flags_by_stage: dict[str, int]
    integrity_decisions: int
    decisions_by_outcome: dict[str, int]


class SupportDashboardOut(ResponseSchema):
    organization_id: str | None
    since: str
    until: str
    tickets_created: int
    by_category: dict[str, int]
    status_changes: int
    by_status: dict[str, int]
    sla_breaches: int
    breaches_by_kind: dict[str, int]
    csat_responses: int
    average_csat: float | None


class HiringDashboardOut(ResponseSchema):
    employer_id: str | None
    organization_id: str | None
    since: str
    until: str
    applications_by_stage: dict[str, int]
    placements: int
    average_placement_ctc: float | None
    offers_extended: int
    offers_accepted: int
    offers_declined: int
    offers_expired: int
    interviews_completed: int
    ai_recommendations: dict[str, int]
    human_overrides: dict[str, int]


class AIUsageDashboardOut(ResponseSchema):
    organization_id: str | None
    since: str
    until: str
    calls: int
    by_capability: dict[str, int]
    total_cost_cents: float
    total_tokens: float


class BillingDashboardOut(ResponseSchema):
    organization_id: str | None
    since: str
    until: str
    invoices_issued: int
    invoiced_amount: float
    invoices_paid: int
    paid_amount: float
    invoices_overdue: int
    overdue_amount: float
    invoices_voided: int
    credit_notes: int
    credit_amount: float
    plans_activated: int
    plans_expired: int


class InstitutionDashboardResponse(SuccessResponse):
    dashboard: InstitutionDashboardOut


class ContentDashboardResponse(SuccessResponse):
    dashboard: ContentDashboardOut


class ExamIntegrityDashboardResponse(SuccessResponse):
    dashboard: ExamIntegrityDashboardOut


class SupportDashboardResponse(SuccessResponse):
    dashboard: SupportDashboardOut


class HiringDashboardResponse(SuccessResponse):
    dashboard: HiringDashboardOut


class AIUsageDashboardResponse(SuccessResponse):
    dashboard: AIUsageDashboardOut


class BillingDashboardResponse(SuccessResponse):
    dashboard: BillingDashboardOut
