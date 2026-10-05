from typing import Any

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.domain.enums import Bloom, QuestionType
from app.schemas.types import PublicIdOut, Timestamp, multiline_text, text

Tag = text(60, examples=["arrays"])
Marks = Field(default=1.0, gt=0, le=1000)


class QuestionCreate(RequestSchema):
    """``body`` is what the student sees and ``answer_key`` what is correct; their shape depends on
    ``question_type`` (see docs/API.md "Question types")."""

    question_type: QuestionType
    text: multiline_text(20_000, examples=["Which data structure gives O(1) average lookup by key?"])  # type: ignore[valid-type]
    body: dict[str, Any] = Field(default_factory=dict)
    answer_key: dict[str, Any] = Field(default_factory=dict)
    explanation: multiline_text(20_000) | None = None  # type: ignore[valid-type]
    default_marks: float = Marks
    difficulty: int = Field(default=3, ge=1, le=5)
    bloom: Bloom | None = None
    skills: list[Tag] = Field(default_factory=list, max_length=20)  # type: ignore[valid-type]
    topics: list[Tag] = Field(default_factory=list, max_length=20)  # type: ignore[valid-type]
    tags: list[Tag] = Field(default_factory=list, max_length=20)  # type: ignore[valid-type]


class QuestionUpdate(RequestSchema):
    """Edits the working draft; on a published question the first edit opens a new draft version."""

    text: multiline_text(20_000) | None = None  # type: ignore[valid-type]
    body: dict[str, Any] | None = None
    answer_key: dict[str, Any] | None = None
    explanation: multiline_text(20_000) | None = None  # type: ignore[valid-type]
    default_marks: float | None = Field(default=None, gt=0, le=1000)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    bloom: Bloom | None = None
    skills: list[Tag] | None = Field(default=None, max_length=20)  # type: ignore[valid-type]
    topics: list[Tag] | None = Field(default=None, max_length=20)  # type: ignore[valid-type]
    tags: list[Tag] | None = Field(default=None, max_length=20)  # type: ignore[valid-type]


class ReviewNote(RequestSchema):
    note: text(500) | None = None  # type: ignore[valid-type]


class RejectNote(RequestSchema):
    note: text(500)  # type: ignore[valid-type]


class QuestionBulkCreate(RequestSchema):
    questions: list[QuestionCreate] = Field(min_length=1, max_length=500)


class QuestionVersionOut(ResponseSchema):
    version_no: int
    status: str
    text: str
    body: dict[str, Any]
    answer_key: dict[str, Any]
    explanation: str | None
    default_marks: float
    difficulty: int
    bloom: str | None
    skills: list[str]
    topics: list[str]
    tags: list[str]
    review_note: str | None
    created_by: PublicIdOut
    created_at: Timestamp
    submitted_at: Timestamp | None
    reviewed_by: PublicIdOut | None
    reviewed_at: Timestamp | None
    published_at: Timestamp | None


class QuestionStatsOut(ResponseSchema):
    sample_size: int
    difficulty_index: float | None = Field(description="Average share of the marks students earned; high = easy")
    discrimination: float | None = Field(description="Top 27% minus bottom 27% of scorers; high = separates well")
    computed_at: Timestamp


class QuestionOut(ResponseSchema):
    question_id: PublicIdOut
    question_type: str
    status: str
    organization_id: PublicIdOut | None
    current_version_no: int | None
    latest_version_no: int
    created_by: PublicIdOut
    created_at: Timestamp
    updated_at: Timestamp
    current: QuestionVersionOut | None = Field(description="The published version tests draw from")
    working: QuestionVersionOut | None = Field(description="The draft or in-review version being edited, if any")
    stats: QuestionStatsOut | None = None


class QuestionListItem(ResponseSchema):
    question_id: PublicIdOut
    question_type: str
    status: str
    current_version_no: int | None
    latest_version_no: int
    latest_version_status: str
    text: str
    difficulty: int
    bloom: str | None
    default_marks: float
    skills: list[str]
    topics: list[str]
    tags: list[str]
    created_at: Timestamp


class QuestionResponse(SuccessResponse):
    question: QuestionOut


class QuestionListResponse(SuccessResponse):
    questions: list[QuestionListItem]
    page_context: PageContext


class QuestionVersionsResponse(SuccessResponse):
    versions: list[QuestionVersionOut]


class QuestionBulkResult(ResponseSchema):
    index: int
    question_id: PublicIdOut | None = None
    error: str | None = None
    details: list[dict[str, Any]] = Field(default_factory=list)


class QuestionBulkResponse(SuccessResponse):
    created: int
    failed: int
    results: list[QuestionBulkResult]


class QuestionStatsResponse(SuccessResponse):
    stats: QuestionStatsOut | None
