from datetime import datetime
from typing import Any

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field, model_validator

from app.domain.enums import (
    Bloom,
    ProctoringLevel,
    QuestionType,
    ResultVisibility,
    ReviewPolicy,
    ScoreCounting,
    SlotType,
    TestKind,
    TimeMode,
)
from app.schemas.question import ReviewNote  # noqa: F401  (re-exported for the endpoints)
from app.schemas.types import PublicIdOut, Timestamp, id_field, multiline_text, text

Tag = text(60, examples=["arrays"])
QuestionId = id_field("question_id", "1755000000005001")
TargetId = id_field("target_id", "1755000000000333")
OrganizationId = id_field("organization_id", "1755000000004003")
UserId = id_field("user_id", "1755000000004001")


class PoolCriteria(RequestSchema):
    """Any-of within a kind, all kinds must match (see docs/API.md "Pools")."""

    types: list[QuestionType] | None = Field(default=None, max_length=10)
    difficulty_min: int | None = Field(default=None, ge=1, le=5)
    difficulty_max: int | None = Field(default=None, ge=1, le=5)
    bloom: list[Bloom] | None = Field(default=None, max_length=6)
    skills: list[Tag] | None = Field(default=None, max_length=20)  # type: ignore[valid-type]
    topics: list[Tag] | None = Field(default=None, max_length=20)  # type: ignore[valid-type]
    tags: list[Tag] | None = Field(default=None, max_length=20)  # type: ignore[valid-type]

    @model_validator(mode="after")
    def _range(self) -> "PoolCriteria":
        if self.difficulty_min and self.difficulty_max and self.difficulty_min > self.difficulty_max:
            raise ValueError("difficulty_min cannot be above difficulty_max")
        return self


class SlotIn(RequestSchema):
    slot_type: SlotType
    question_id: QuestionId | None = None  # type: ignore[valid-type]
    criteria: PoolCriteria | None = None
    count: int = Field(default=1, ge=1, le=100, description="Pool slots only: questions drawn per student")
    marks: float | None = Field(default=None, gt=0, le=1000, description="Per question; fixed slots default to the question's")

    @model_validator(mode="after")
    def _shape(self) -> "SlotIn":
        if self.slot_type == SlotType.FIXED:
            if self.question_id is None or self.criteria is not None:
                raise ValueError("A fixed slot names one question_id and no criteria")
            if self.count != 1:
                raise ValueError("A fixed slot is one question; leave count at 1")
        else:
            if self.criteria is None or self.question_id is not None:
                raise ValueError("A pool slot gives criteria and no question_id")
            if self.marks is None:
                raise ValueError("A pool slot needs marks")
        return self


class SectionIn(RequestSchema):
    title: text(200)  # type: ignore[valid-type]
    instructions: multiline_text(5_000) | None = None  # type: ignore[valid-type]
    time_limit_minutes: int | None = Field(default=None, ge=1, le=600, description="Per-section timing only")
    slots: list[SlotIn] = Field(min_length=1, max_length=100)


class SectionsReplace(RequestSchema):
    sections: list[SectionIn] = Field(min_length=1, max_length=50)


class _Rules(RequestSchema):
    time_mode: TimeMode = TimeMode.OVERALL
    duration_minutes: int | None = Field(default=None, ge=1, le=1_440, description="Overall timing only")
    pass_mark_percent: int = Field(default=60, ge=0, le=100)
    max_attempts: int = Field(default=3, ge=0, le=100, description="0 = unlimited")
    cooldown_hours: int = Field(default=0, ge=0, le=24 * 90)
    score_counting: ScoreCounting = ScoreCounting.HIGHEST
    negative_marking_percent: int = Field(default=0, ge=0, le=100, description="Share of a question's marks lost on a wrong answer")
    shuffle_questions: bool = False
    shuffle_options: bool = False
    result_visibility: ResultVisibility = ResultVisibility.IMMEDIATE
    review_policy: ReviewPolicy = ReviewPolicy.NONE
    proctoring_level: ProctoringLevel = ProctoringLevel.NONE
    proctoring_screen_share: bool = Field(default=False, description="Strict proctoring only: the student shares their screen for the whole test")
    requires_schedule: bool = False


class TestCreate(_Rules):
    __test__ = False

    title: text(200, examples=["JavaScript Fundamentals: module test"])  # type: ignore[valid-type]
    description: multiline_text(5_000) | None = None  # type: ignore[valid-type]
    instructions: multiline_text(10_000) | None = None  # type: ignore[valid-type]
    kind: TestKind
    target_id: TargetId | None = Field(  # type: ignore[valid-type]
        default=None, description="topic / module / course id from catalog-service (topic, module and final tests)"
    )
    sections: list[SectionIn] | None = Field(default=None, max_length=50)


class TestUpdate(RequestSchema):
    __test__ = False

    title: text(200) | None = None  # type: ignore[valid-type]
    description: multiline_text(5_000) | None = None  # type: ignore[valid-type]
    instructions: multiline_text(10_000) | None = None  # type: ignore[valid-type]
    kind: TestKind | None = None
    target_id: TargetId | None = None  # type: ignore[valid-type]
    time_mode: TimeMode | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1_440)
    pass_mark_percent: int | None = Field(default=None, ge=0, le=100)
    max_attempts: int | None = Field(default=None, ge=0, le=100)
    cooldown_hours: int | None = Field(default=None, ge=0, le=24 * 90)
    score_counting: ScoreCounting | None = None
    negative_marking_percent: int | None = Field(default=None, ge=0, le=100)
    shuffle_questions: bool | None = None
    shuffle_options: bool | None = None
    result_visibility: ResultVisibility | None = None
    review_policy: ReviewPolicy | None = None
    proctoring_level: ProctoringLevel | None = None
    proctoring_screen_share: bool | None = None
    requires_schedule: bool | None = None


class ScheduleCreate(RequestSchema):
    title: text(200) | None = None  # type: ignore[valid-type]
    organization_id: OrganizationId | None = Field(default=None, description="Restrict to one institution; empty = all")  # type: ignore[valid-type]
    starts_at: datetime
    ends_at: datetime
    enforce_end: bool = True
    results_release_at: datetime | None = None

    @model_validator(mode="after")
    def _window(self) -> "ScheduleCreate":
        for value in (self.starts_at, self.ends_at, self.results_release_at):
            if value is not None and value.tzinfo is None:
                raise ValueError("Give times with a timezone, e.g. 2026-10-01T09:00:00Z")
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class ScheduleUpdate(RequestSchema):
    title: text(200) | None = None  # type: ignore[valid-type]
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    enforce_end: bool | None = None
    results_release_at: datetime | None = None


class AssignmentCreate(RequestSchema):
    """job-portal-service inviting a shortlisted candidate to a hiring assessment."""

    test_id: id_field("test_id", "1755000000000555")  # type: ignore[valid-type]
    user_id: UserId  # type: ignore[valid-type]
    reference: text(100) | None = None  # type: ignore[valid-type]
    opens_at: datetime | None = None
    expires_at: datetime | None = None
    max_attempts: int | None = Field(default=None, ge=1, le=20)


# ----------------------------------------------------------------------------- responses


class SlotOut(ResponseSchema):
    position: int
    slot_type: str
    question_id: PublicIdOut | None
    criteria: dict[str, Any] | None
    count: int
    marks: float


class SectionOut(ResponseSchema):
    section_id: PublicIdOut = Field(validation_alias="public_id")
    position: int
    title: str
    instructions: str | None
    time_limit_minutes: int | None
    slots: list[SlotOut]


class TestListItem(ResponseSchema):
    __test__ = False

    test_id: PublicIdOut = Field(validation_alias="public_id")
    title: str
    kind: str
    status: str
    target_type: str | None
    target_id: PublicIdOut | None
    organization_id: PublicIdOut | None
    time_mode: str
    duration_minutes: int | None
    pass_mark_percent: int
    max_attempts: int
    proctoring_level: str
    total_marks: float | None
    question_count: int | None
    created_at: Timestamp
    published_at: Timestamp | None


class TestOut(TestListItem):
    __test__ = False

    description: str | None
    instructions: str | None
    cooldown_hours: int
    score_counting: str
    negative_marking_percent: int
    shuffle_questions: bool
    shuffle_options: bool
    result_visibility: str
    review_policy: str
    proctoring_screen_share: bool
    requires_schedule: bool
    review_note: str | None
    created_by: PublicIdOut
    updated_at: Timestamp
    sections: list[SectionOut]


class TestIssue(ResponseSchema):
    __test__ = False

    field: str
    code: str
    message: str


class TestResponse(SuccessResponse):
    __test__ = False

    test: TestOut


class TestListResponse(SuccessResponse):
    __test__ = False

    tests: list[TestListItem]
    page_context: PageContext


class TestValidationResponse(SuccessResponse):
    __test__ = False

    valid: bool
    issues: list[TestIssue]
    total_marks: float | None
    question_count: int | None


class ScheduleOut(ResponseSchema):
    schedule_id: PublicIdOut = Field(validation_alias="public_id")
    test_id: PublicIdOut
    title: str | None
    organization_id: PublicIdOut | None
    starts_at: Timestamp
    ends_at: Timestamp
    enforce_end: bool
    results_release_at: Timestamp | None
    cancelled_at: Timestamp | None
    created_at: Timestamp


class ScheduleResponse(SuccessResponse):
    schedule: ScheduleOut


class ScheduleListResponse(SuccessResponse):
    schedules: list[ScheduleOut]


class AssignmentOut(ResponseSchema):
    test_id: PublicIdOut
    user_id: PublicIdOut
    reference: str | None
    opens_at: Timestamp | None
    expires_at: Timestamp | None
    max_attempts: int | None


class AssignmentResponse(SuccessResponse):
    assignment: AssignmentOut
