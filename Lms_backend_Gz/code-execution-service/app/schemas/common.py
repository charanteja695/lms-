"""List/filter query params. Domain-specific, so it stays per-service (see lms-backend/README.md);
the response envelope shapes themselves (SuccessResponse, PageContext, ...) come from lms_common."""

from lms_common.envelopes import SortOrder
from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import Difficulty, JobStatus, ProblemStatus, ProblemType, Verdict
from app.schemas.types import id_field

MAX_LIST_WINDOW = 10_000


class _PagedQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sort_order: SortOrder = SortOrder.DESC
    page: int = Field(default=1, ge=1, le=MAX_LIST_WINDOW)
    per_page: int = Field(default=20, ge=1, le=100)


class ProblemQuery(_PagedQuery):
    status: ProblemStatus | None = Field(default=None, description="Authors and reviewers only; students see published")
    difficulty: Difficulty | None = None
    problem_type: ProblemType | None = None
    tag: str | None = Field(default=None, max_length=30)
    search: str | None = Field(default=None, max_length=100)
    solved: bool | None = Field(default=None, description="Only problems this user has (true) or has not (false) solved")


class SubmissionQuery(_PagedQuery):
    problem_id: id_field("problem_id", "1755000000006555") | None = None  # type: ignore[valid-type]
    status: JobStatus | None = None
    verdict: Verdict | None = None


class ReviewSubmissionQuery(SubmissionQuery):
    user_id: id_field("user_id", "1755000000004001") | None = None  # type: ignore[valid-type]
    reference: str | None = Field(default=None, max_length=100)
    flagged: bool | None = None
