from datetime import date
from typing import Annotated, Any

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.domain.enums import ApplicationStatus, EmploymentType
from app.schemas.fields import AwareDatetime
from app.schemas.job import MatchOut
from app.schemas.types import PublicIdOut, Timestamp, id_field, multiline_text, text

ApplicationId = id_field("Application", "1755000000060001")


# ---------------------------------------------------------------- requests
class ApplyRequest(RequestSchema):
    resume_id: id_field("Resume", "1755000000050001")  # type: ignore[valid-type]
    cover_note: multiline_text(2_000) | None = None  # type: ignore[valid-type]


class WithdrawRequest(RequestSchema):
    note: text(500) | None = None  # type: ignore[valid-type]


class TransitionRequest(RequestSchema):
    to: ApplicationStatus
    note: text(500) | None = None  # type: ignore[valid-type]
    hr_interview_at: AwareDatetime | None = Field(default=None, description="When moving to hr_interview: the scheduled time")


class NoteIn(RequestSchema):
    body: multiline_text(2_000)  # type: ignore[valid-type]


class BulkShortlistRequest(RequestSchema):
    application_ids: Annotated[list[ApplicationId], Field(min_length=1, max_length=500)] | None = None  # type: ignore[valid-type]
    threshold: int | None = Field(default=None, ge=0, le=100, description="Or: everyone still undecided whose screening score is at least this")


class RejectRequest(RequestSchema):
    application_ids: Annotated[list[ApplicationId], Field(min_length=1, max_length=500)]  # type: ignore[valid-type]
    reason: text(500)  # type: ignore[valid-type]
    confirm: bool = Field(description="Must be true. A person confirms every rejection; the AI's recommendation never rejects anyone")
    threshold: int | None = Field(default=None, ge=0, le=100, description="Recorded in the batch if the recruiter chose these by a threshold")


class OfferRequest(RequestSchema):
    ctc: int = Field(ge=0, description="Whole units per year")
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    joining_date: date | None = None
    valid_days: int | None = Field(default=None, ge=1, le=60)
    role_title: text(160) | None = None  # type: ignore[valid-type]
    note: text(500) | None = None  # type: ignore[valid-type]


class OfferResponseRequest(RequestSchema):
    accept: bool
    note: text(500) | None = None  # type: ignore[valid-type]


class PreferencesIn(RequestSchema):
    locations: Annotated[list[text(80)], Field(max_length=10)] | None = None  # type: ignore[valid-type]
    open_to_remote: bool | None = None
    roles: Annotated[list[text(80)], Field(max_length=5)] | None = None  # type: ignore[valid-type]
    min_ctc: int | None = Field(default=None, ge=0)
    employment_types: Annotated[list[EmploymentType], Field(max_length=3)] | None = None
    open_to_work: bool | None = Field(default=None, description="false: no recommendations and no match notifications")


# ---------------------------------------------------------------- responses
class StageOut(ResponseSchema):
    from_status: str | None
    to_status: str
    actor: str
    note: str | None
    created_at: Timestamp


class OfferOut(ResponseSchema):
    offer_id: PublicIdOut = Field(validation_alias="public_id")
    ctc: int
    currency: str
    joining_date: date | None
    role_title: str
    note: str | None
    status: str
    expires_at: Timestamp
    responded_at: Timestamp | None


class AssessmentOut(ResponseSchema):
    test_id: PublicIdOut | None
    invite_state: str | None
    percent: float | None
    result: str | None
    integrity: str | None


class MyApplicationOut(ResponseSchema):
    application_id: PublicIdOut
    job_id: PublicIdOut
    job_title: str
    company_name: str | None
    status: str
    match_score: int | None
    match_explanation: list[str] | None
    resume_version_no: int
    assessment: AssessmentOut | None = None
    offer: OfferOut | None = None
    history: list[StageOut] = Field(default_factory=list)
    applied_at: Timestamp
    status_changed_at: Timestamp | None


class MyApplicationResponse(SuccessResponse):
    application: MyApplicationOut


class MyApplicationPage(SuccessResponse):
    applications: list[MyApplicationOut]
    page_context: PageContext


class ScreeningOut(ResponseSchema):
    score: int | None
    recommendation: str | None
    source: str | None
    reasons: list[str]
    red_flags: list[str]


class CandidateSummary(ResponseSchema):
    user_id: PublicIdOut
    name: str
    email: str | None


class RecruiterApplicationOut(ResponseSchema):
    application_id: PublicIdOut
    job_id: PublicIdOut
    candidate: CandidateSummary
    status: str
    match_score: int | None
    match_explanation: list[str] | None
    screening: ScreeningOut
    assessment: AssessmentOut | None
    interview: dict[str, Any] | None
    hr_interview_at: Timestamp | None = None
    cover_note: str | None
    resume_version_no: int
    applied_at: Timestamp
    status_changed_at: Timestamp | None
    decision_reason: str | None = None


class RecruiterApplicationDetail(RecruiterApplicationOut):
    resume: dict[str, Any]
    history: list[StageOut]
    notes: list[dict[str, Any]]
    offer: OfferOut | None = None


class RecruiterApplicationResponse(SuccessResponse):
    application: RecruiterApplicationDetail


class RecruiterApplicationPage(SuccessResponse):
    applications: list[RecruiterApplicationOut]
    page_context: PageContext


class RankedApplication(ResponseSchema):
    application: RecruiterApplicationOut


class RankingOut(ResponseSchema):
    shortlist_at: int
    reject_below: int
    shortlist: list[RecruiterApplicationOut]
    review: list[RecruiterApplicationOut]
    reject: list[RecruiterApplicationOut]
    unscreened: list[RecruiterApplicationOut]
    note: str = "These are recommendations. Nobody is shortlisted or rejected until a person does it."


class RankingResponse(SuccessResponse):
    ranking: RankingOut


class BatchOut(ResponseSchema):
    batch_id: PublicIdOut = Field(validation_alias="public_id")
    reason: str
    application_ids: list[PublicIdOut]
    recommended_count: int
    not_recommended_count: int
    threshold: int | None
    created_at: Timestamp


class BatchResponse(SuccessResponse):
    batch: BatchOut


class BulkResult(SuccessResponse):
    count: int
    application_ids: list[str]


class OfferResponse(SuccessResponse):
    offer: OfferOut


class NoteResponse(SuccessResponse):
    note: dict[str, Any]


class DecisionOut(ResponseSchema):
    application_id: PublicIdOut | None = None
    kind: str
    source: str
    model: str | None
    prompt_key: str | None
    prompt_version: int | None
    input_digest: str
    score: int | None
    recommendation: str
    output: dict[str, Any]
    created_at: Timestamp


class DecisionPage(SuccessResponse):
    decisions: list[DecisionOut]


class PreferencesOut(ResponseSchema):
    locations: list[str]
    open_to_remote: bool
    roles: list[str]
    min_ctc: int | None
    employment_types: list[str]
    open_to_work: bool


class PreferencesResponse(SuccessResponse):
    preferences: PreferencesOut


class MatchedJob(ResponseSchema):
    match: MatchOut


class FunnelResponse(SuccessResponse):
    job_id: PublicIdOut
    by_status: dict[str, int]
    total: int
    placed: int
    openings: int


class InstitutionApplicationOut(ResponseSchema):
    """What an institution's staff see about their students' applications: who, where, and how far. No screening, no notes."""

    application_id: PublicIdOut
    student: CandidateSummary
    job_id: PublicIdOut
    job_title: str
    company_name: str | None
    drive_id: PublicIdOut | None
    status: str
    applied_at: Timestamp
    status_changed_at: Timestamp | None
    ctc: int | None = None
    currency: str | None = None


class InstitutionApplicationPage(SuccessResponse):
    applications: list[InstitutionApplicationOut]
    page_context: PageContext


class InstitutionSummaryResponse(SuccessResponse):
    students_applied: int
    applications: int
    by_status: dict[str, int]
    placed: int
    placed_students: int
    employers: int
