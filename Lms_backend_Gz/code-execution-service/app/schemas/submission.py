from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field, field_validator

from app.domain.enums import Priority
from app.schemas.run import LanguageRef, SourceCode
from app.schemas.types import PublicIdOut, Timestamp, id_field, text

InternalProblemId = id_field("problem_id", "1755000000006555")
InternalUserId = id_field("user_id", "1755000000004001")
InternalOrganizationId = id_field("organization_id", "1755000000004003")
Reference = text(100, examples=["attempt:1755000000009001"])


class SubmissionCreate(RequestSchema):
    language: LanguageRef
    source: SourceCode


class InternalSubmissionCreate(RequestSchema):
    """assessment-service submitting on a student's behalf. ``reference`` is echoed in ``submission.judged`` so
    the caller can match the verdict to its attempt."""

    user_id: InternalUserId  # type: ignore[valid-type]
    organization_id: InternalOrganizationId | None = None  # type: ignore[valid-type]
    problem_id: InternalProblemId  # type: ignore[valid-type]
    language: LanguageRef
    source: SourceCode
    reference: Reference  # type: ignore[valid-type]
    priority: Priority = Field(default=Priority.EXAM, description="2 = exam lane, 1 = practice submissions")

    @field_validator("priority")
    @classmethod
    def _submission_lane(cls, value: Priority) -> Priority:
        if value == Priority.PRACTICE:
            raise ValueError("Lane 0 is for runs; a submission uses 1 or 2")
        return value


class CaseResultOut(ResponseSchema):
    position: int
    is_sample: bool
    verdict: str
    time_ms: int | None
    memory_kb: int | None
    message: str | None
    input: str | None = Field(default=None, validation_alias="sample_input", description="Samples only")
    expected: str | None = Field(default=None, validation_alias="sample_expected", description="Samples only")
    actual: str | None = Field(default=None, validation_alias="sample_actual", description="Samples only")


class SubmissionListItem(ResponseSchema):
    submission_id: PublicIdOut = Field(validation_alias="public_id")
    problem_id: PublicIdOut = Field(validation_alias="problem_public_id")
    language: str = Field(validation_alias="language_code")
    status: str
    verdict: str | None
    score: int
    passed_count: int
    total_count: int
    created_at: Timestamp


class SubmissionOut(SubmissionListItem):
    source: str
    time_ms: int | None
    memory_kb: int | None
    compile_output: str | None
    message: str | None
    judged_at: Timestamp | None
    results: list[CaseResultOut]


class ReviewSubmissionOut(SubmissionOut):
    """Reviewers: adds who submitted and the plagiarism signal."""

    user_id: PublicIdOut
    organization_id: PublicIdOut | None
    reference: str | None
    flagged: bool
    similarity_percent: int | None
    similar_to_submission_id: PublicIdOut | None = Field(default=None, validation_alias="similar_to_public_id")


class SubmissionResponse(SuccessResponse):
    submission: SubmissionOut


class ReviewSubmissionResponse(SuccessResponse):
    submission: ReviewSubmissionOut


class SubmissionListResponse(SuccessResponse):
    submissions: list[SubmissionListItem]
    page_context: PageContext


class ReviewSubmissionListItem(SubmissionListItem):
    user_id: PublicIdOut
    reference: str | None
    flagged: bool
    similarity_percent: int | None
    similar_to_submission_id: PublicIdOut | None = Field(default=None, validation_alias="similar_to_public_id")


class ReviewSubmissionListResponse(SuccessResponse):
    submissions: list[ReviewSubmissionListItem]
    page_context: PageContext


class SimilarMatchOut(ResponseSchema):
    submission_id: PublicIdOut
    user_id: PublicIdOut
    similarity_percent: int
    verdict: str | None
    created_at: Timestamp


class SimilarMatchesResponse(SuccessResponse):
    matches: list[SimilarMatchOut]
