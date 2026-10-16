from typing import Any, Literal

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field, model_validator

from app.schemas.types import PublicIdOut, Timestamp, id_field, multiline_text, text

QuestionId = id_field("question_id", "1755000000005001")


class AttemptCreate(RequestSchema):
    start_now: bool = Field(default=False, description="Prepare the paper and start the clock in one call")


class AnswerIn(RequestSchema):
    """``response`` depends on the question type (docs/API.md "Answers"); null or empty clears the answer.
    ``revision`` is a counter the client bumps on every change: an older revision never overwrites a newer one."""

    response: dict[str, Any] | None = None
    revision: int = Field(default=0, ge=0, le=2_000_000_000)
    flagged: bool = Field(default=False, description="Marked for review by the student")


class AnswerBatchItem(AnswerIn):
    question_id: QuestionId  # type: ignore[valid-type]


class AnswerBatchIn(RequestSchema):
    answers: list[AnswerBatchItem] = Field(min_length=1, max_length=50)


class FileUploadUrlIn(RequestSchema):
    filename: text(200)  # type: ignore[valid-type]
    content_type: text(100, examples=["application/pdf"])  # type: ignore[valid-type]
    size_bytes: int = Field(gt=0)


class GradeIn(RequestSchema):
    """Rubric questions: per-criterion ``rubric_scores``. Otherwise ``marks``. An exam manager overriding an automatic
    grade must also give ``feedback`` saying why."""

    marks: float | None = Field(default=None, ge=0, le=1_000)
    rubric_scores: dict[str, float] | None = None
    feedback: multiline_text(5_000) | None = None  # type: ignore[valid-type]

    @model_validator(mode="after")
    def _one_way(self) -> "GradeIn":
        if (self.marks is None) == (self.rubric_scores is None):
            raise ValueError("Give either marks or rubric_scores")
        return self


class ReasonIn(RequestSchema):
    reason: text(300) | None = None  # type: ignore[valid-type]


class IntegrityDecisionIn(RequestSchema):
    decision: Literal["clear", "reviewed_ok", "invalidated"]


class SavedAnswerOut(ResponseSchema):
    question_id: PublicIdOut
    status: Literal["saved", "stale", "rejected"]
    revision: int
    error: dict[str, Any] | None = None


class SavedAnswersResponse(SuccessResponse):
    answers: list[SavedAnswerOut]
    server_time: Timestamp


class SectionStateOut(ResponseSchema):
    section_id: PublicIdOut
    position: int
    title: str
    time_limit_minutes: int | None
    started_at: Timestamp | None = None
    deadline_at: Timestamp | None = None
    finished_at: Timestamp | None = None
    is_current: bool = False


class AttemptStateOut(ResponseSchema):
    attempt_id: PublicIdOut
    test_id: PublicIdOut
    test_title: str
    test_kind: str
    status: str
    attempt_no: int
    proctoring_level: str
    time_mode: str
    started_at: Timestamp | None
    deadline_at: Timestamp | None
    remaining_seconds: int | None = Field(description="Server-computed; the server clock is the authority")
    server_time: Timestamp
    resume_count: int
    opens_at: Timestamp | None = Field(default=None, description="Waiting room: when the exam starts")
    submitted_at: Timestamp | None
    submit_reason: str | None
    results_released: bool
    total_questions: int
    sections: list[SectionStateOut] = Field(default_factory=list)


class PaperQuestionOut(ResponseSchema):
    question_id: str
    position: int
    section_id: str
    section_position: int
    question_type: str
    text: str
    marks: float
    body: dict[str, Any]
    answer: dict[str, Any] | None = None


class AttemptResponse(SuccessResponse):
    attempt: AttemptStateOut


class AttemptPaperResponse(SuccessResponse):
    attempt: AttemptStateOut
    questions: list[PaperQuestionOut]


class ReviewQuestionOut(ResponseSchema):
    question_id: PublicIdOut
    position: int
    question_type: str
    text: str
    body: dict[str, Any]
    marks: float
    marks_awarded: float | None
    is_correct: bool | None
    grading_status: str | None
    feedback: str | None
    rubric_scores: dict[str, Any] | None
    response: dict[str, Any] | None
    answer_key: dict[str, Any] | None = None
    explanation: str | None = None


class ResultOut(ResponseSchema):
    attempt_id: PublicIdOut
    test_id: PublicIdOut
    test_title: str
    status: str
    released: bool
    message: str | None = None
    result: str | None = None
    score: float | None = None
    max_score: float | None = None
    percent: float | None = None
    pass_mark_percent: int | None = None
    integrity_status: str | None = None
    submitted_at: Timestamp | None
    released_at: Timestamp | None = None
    questions: list[ReviewQuestionOut] | None = None


class ResultResponse(SuccessResponse):
    result: ResultOut


class AttemptListItem(ResponseSchema):
    attempt_id: PublicIdOut = Field(validation_alias="public_id")
    test_id: PublicIdOut = Field(validation_alias="test_public_id")
    user_id: PublicIdOut
    organization_id: PublicIdOut | None
    attempt_no: int
    status: str
    result: str
    score: float | None
    max_score: float | None
    percent: float | None
    integrity_status: str
    plagiarism_flagged: bool
    started_at: Timestamp | None
    submitted_at: Timestamp | None
    results_visible_at: Timestamp | None


class AttemptListResponse(SuccessResponse):
    attempts: list[AttemptListItem]
    page_context: PageContext


class ResultsSummaryRequest(RequestSchema):
    user_ids: list[id_field("user_id", "1755000000004001")] = Field(min_length=1, max_length=500, description="The students, e.g. one section's roster")  # type: ignore[valid-type]
    test_id: id_field("test_id", "1755000000000555") | None = None  # type: ignore[valid-type]


class ResultsTestOut(ResponseSchema):
    test_id: PublicIdOut
    title: str
    kind: str
    pass_mark_percent: int


class ResultsRowOut(ResponseSchema):
    user_id: PublicIdOut
    test_id: PublicIdOut
    attempts: int
    best_percent: float | None
    best_score: float | None
    max_score: float | None
    passed: bool
    last_submitted_at: Timestamp | None


class ResultsSummaryResponse(SuccessResponse):
    tests: list[ResultsTestOut]
    rows: list[ResultsRowOut] = Field(description="One row per student and test they attempted; a student with no attempts has none")


class AttemptEventOut(ResponseSchema):
    event_type: str
    actor_user_id: PublicIdOut | None
    ip_address: str | None
    detail: dict[str, Any] | None
    created_at: Timestamp


class AttemptEventsResponse(SuccessResponse):
    events: list[AttemptEventOut]


class GradingQueueItem(ResponseSchema):
    attempt_id: PublicIdOut
    test_id: PublicIdOut
    user_id: PublicIdOut
    question_id: PublicIdOut
    question_type: str
    text: str
    marks: float
    rubric: list[dict[str, Any]]
    response: dict[str, Any] | None
    submitted_at: Timestamp | None


class GradingQueueResponse(SuccessResponse):
    items: list[GradingQueueItem]
    page_context: PageContext


class GradedAnswerOut(ResponseSchema):
    question_id: PublicIdOut
    marks_awarded: float | None
    max_marks: float | None
    grading_status: str | None
    feedback: str | None
    rubric_scores: dict[str, Any] | None


class GradedAnswerResponse(SuccessResponse):
    answer: GradedAnswerOut
    attempt: AttemptListItem


class FileUploadOut(ResponseSchema):
    key: str
    upload: dict[str, Any]
    expires_in: int


class FileUploadResponse(SuccessResponse):
    file: FileUploadOut


class FileDownloadOut(ResponseSchema):
    filename: str
    url: str
    expires_in: int


class FileDownloadResponse(SuccessResponse):
    file: FileDownloadOut


class MyTestOut(ResponseSchema):
    test_id: PublicIdOut
    title: str
    kind: str
    description: str | None
    time_mode: str
    duration_minutes: int | None
    pass_mark_percent: int
    question_count: int | None
    total_marks: float | None
    proctoring_level: str
    can_start: bool
    reason: str | None
    message: str | None
    attempts_used: int
    attempts_left: int | None
    next_available_at: Timestamp | None
    opens_at: Timestamp | None
    open_attempt_id: PublicIdOut | None
    best_percent: float | None


class MyTestsResponse(SuccessResponse):
    tests: list[MyTestOut]
    page_context: PageContext


class MyTestResponse(SuccessResponse):
    test: MyTestOut
    instructions: str | None
    sections: list[dict[str, Any]]


class ReleaseResultsResponse(SuccessResponse):
    scheduled: int


class TestAnalyticsOut(ResponseSchema):
    attempts: dict[str, int]
    graded: int
    average_percent: float | None
    pass_rate_percent: float | None
    average_minutes: float | None
    distribution: list[dict[str, Any]]
    plagiarism_flagged: int
    integrity_pending: int
    questions: list[dict[str, Any]]


class TestAnalyticsResponse(SuccessResponse):
    analytics: TestAnalyticsOut


class PlagiarismItem(ResponseSchema):
    attempt_id: PublicIdOut
    user_id: PublicIdOut
    question_id: PublicIdOut
    language: str
    verdict: str | None
    similarity_percent: int | None
    similar_to_submission_id: PublicIdOut | None
    code_submission_id: PublicIdOut | None


class PlagiarismResponse(SuccessResponse):
    flagged: list[PlagiarismItem]


class QueueOut(ResponseSchema):
    grading: dict[str, int]
    coding: dict[str, int]
    answers_waiting_to_flush: int


class QueueResponse(SuccessResponse):
    queue: QueueOut
