"""Taking and reviewing an interview: consent, turns, the coding round, the report, and appeals."""

from typing import Any

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.fields import AwareDatetime
from app.schemas.types import PublicIdOut, Timestamp, id_field, raw_text, slug, text

InterviewPlanId = id_field("Interview plan", "1755000000000777")


class ConsentRequest(RequestSchema):
    version: text(20)  # type: ignore[valid-type]
    recording: bool = False


class ConsentOut(ResponseSchema):
    version: str
    text: str
    recording_required: bool
    instructions: str | None


class AnswerText(RequestSchema):
    """A typed turn (an audio one is posted as multipart form data instead)."""

    text: raw_text(4_000)  # type: ignore[valid-type]
    want_audio: bool = False


class CodeRunRequest(RequestSchema):
    language: slug(20)  # type: ignore[valid-type]
    source: raw_text(20_000)  # type: ignore[valid-type]
    stdin: raw_text(4_000) = ""  # type: ignore[valid-type]


class TurnOut(ResponseSchema):
    seq: int
    round: str
    speaker: str
    kind: str
    text: str
    elapsed_ms: int
    via: str
    meta: dict[str, Any] | None


class TurnPair(ResponseSchema):
    """One exchange: the turn just recorded and (unless the interview ended first) the interviewer's reply."""

    turn: TurnOut
    reply: TurnOut | None
    finished: bool
    degraded: bool = Field(description="The model could not produce a follow-up: the director moved on to the next core question")
    audio: str | None = Field(default=None, description="Base64, only when asked for and speech is configured")
    audio_type: str | None = None
    audio_error: str | None = None


class CodeRunOut(ResponseSchema):
    code: TurnOut
    result: TurnOut
    run_id: PublicIdOut
    status: str
    outcome: str | None
    stdout: str
    stderr: str
    compile_output: str
    time_ms: int | None


class CurrentRoundOut(ResponseSchema):
    """The round the interview is in: what the candidate's screen needs (a coding round shows the editor with these languages)."""

    key: str
    type: str
    minutes: int
    languages: list[str]
    number: int
    total: int


class InterviewOut(ResponseSchema):
    interview_id: PublicIdOut
    plan_id: PublicIdOut
    kind: str
    status: str
    attempt_no: int
    role: str
    duration_minutes: int
    invite_expires_at: Timestamp | None
    started_at: Timestamp | None
    ends_at: Timestamp | None
    completed_at: Timestamp | None
    round_index: int
    turn_count: int
    code_runs: int
    feedback_released: bool
    retake_granted: bool
    created_at: Timestamp
    current_round: CurrentRoundOut | None = None


class TimeLeftOut(ResponseSchema):
    round_seconds_left: int
    interview_seconds_left: int


class ReportOut(ResponseSchema):
    """The candidate's own report. The recommendation is never shown here — only the recruiter and careers managers see it (docs/PRODUCT.md §5.8)."""

    released: bool
    summary: str | None = None
    criterion_scores: dict[str, float] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    improvement_plan: str | None = None


class InterviewResponse(SuccessResponse):
    interview: InterviewOut


class InterviewPage(SuccessResponse):
    interviews: list[InterviewOut]
    page_context: PageContext


class ConsentResponse(SuccessResponse):
    consent: ConsentOut


class TurnResponse(SuccessResponse):
    turns: TurnPair


class CodeRunResponse(SuccessResponse):
    run: CodeRunOut


class ReportResponse(SuccessResponse):
    report: ReportOut


class TranscriptResponse(SuccessResponse):
    turns: list[TurnOut]


# ---------------------------------------------------------------- the employer's / careers manager's side
class EvaluationOut(ResponseSchema):
    status: str
    model: str | None
    prompt_version: int | None
    rounds: list[dict[str, Any]]
    criterion_scores: dict[str, float]
    overall_score: float | None
    recommendation: str | None
    summary: str | None
    strengths: list[str]
    improvements: list[str]
    flags: list[str]
    invalid_quotes: int
    total_quotes: int
    last_error: str | None


class EmployerInterviewOut(InterviewOut):
    application_id: PublicIdOut | None
    job_id: PublicIdOut | None
    user_id: PublicIdOut
    integrity_status: str | None
    reviewed_by: PublicIdOut | None
    reviewed_at: Timestamp | None
    final_recommendation: str | None
    review_note: str | None


class EmployerInterviewDetail(EmployerInterviewOut):
    transcript: list[TurnOut]
    evaluation: EvaluationOut | None


class EmployerInterviewResponse(SuccessResponse):
    interview: EmployerInterviewOut


class EmployerInterviewDetailResponse(SuccessResponse):
    interview: EmployerInterviewDetail


class EmployerInterviewPage(SuccessResponse):
    interviews: list[EmployerInterviewOut]
    page_context: PageContext


class ReviewRequest(RequestSchema):
    recommendation: str | None = Field(default=None, description="Send none to confirm the AI's recommendation, or one of strong_yes/yes/lean_no/no to override it")
    note: text(500) | None = Field(default=None, description="Required when overriding")  # type: ignore[valid-type]
    release_feedback: bool = False


class AppealRequest(RequestSchema):
    reason: text(1_000, min_length=10)  # type: ignore[valid-type]


class DecideAppealRequest(RequestSchema):
    uphold: bool
    note: text(500) | None = Field(default=None, description="Required when the appeal is denied: the candidate reads it")  # type: ignore[valid-type]


class AppealOut(ResponseSchema):
    appeal_id: PublicIdOut
    interview_id: PublicIdOut
    user_id: PublicIdOut
    reason: str
    status: str
    decided_by: PublicIdOut | None
    decided_at: Timestamp | None
    decision_note: str | None
    created_at: Timestamp


class AppealResponse(SuccessResponse):
    appeal: AppealOut


class OpenAppealOut(AppealOut):
    interview: EmployerInterviewOut


class AppealPage(SuccessResponse):
    appeals: list[OpenAppealOut]
    page_context: PageContext


class MockInterviewCreate(RequestSchema):
    plan_id: InterviewPlanId  # type: ignore[valid-type]


_ = AwareDatetime  # re-exported for endpoints that filter by date range
