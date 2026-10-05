"""List/filter query params. Domain-specific, so it stays per-service (see lms-backend/README.md);
the response envelope shapes themselves (SuccessResponse, PageContext, ...) come from lms_common."""

from lms_common.envelopes import SortOrder
from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    AttemptResult,
    AttemptStatus,
    Bloom,
    IntegrityStatus,
    QuestionStatus,
    QuestionType,
    TestKind,
    TestStatus,
    VersionStatus,
)
from app.schemas.types import id_field

MAX_LIST_WINDOW = 10_000


class _PagedQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sort_order: SortOrder = SortOrder.DESC
    page: int = Field(default=1, ge=1, le=MAX_LIST_WINDOW)
    per_page: int = Field(default=20, ge=1, le=100)


class QuestionQuery(_PagedQuery):
    question_type: QuestionType | None = None
    status: QuestionStatus | None = None
    version_status: VersionStatus | None = Field(default=None, description="Status of the latest (working) version")
    difficulty_min: int | None = Field(default=None, ge=1, le=5)
    difficulty_max: int | None = Field(default=None, ge=1, le=5)
    bloom: Bloom | None = None
    skill: str | None = Field(default=None, max_length=60)
    topic: str | None = Field(default=None, max_length=60)
    tag: str | None = Field(default=None, max_length=60)
    search: str | None = Field(default=None, max_length=100)
    organization_id: id_field("organization_id", "1755000000004003") | None = Field(  # type: ignore[valid-type]
        default=None, description="Super admins only: an employer's bank instead of the platform's"
    )


class TestQuery(_PagedQuery):
    __test__ = False

    kind: TestKind | None = None
    status: TestStatus | None = None
    target_id: id_field("target_id", "1755000000000333") | None = None  # type: ignore[valid-type]
    search: str | None = Field(default=None, max_length=100)
    organization_id: id_field("organization_id", "1755000000004003") | None = None  # type: ignore[valid-type]


class MyTestsQuery(_PagedQuery):
    kind: TestKind | None = None
    target_id: id_field("target_id", "1755000000000333") | None = None  # type: ignore[valid-type]


class AttemptQuery(_PagedQuery):
    test_id: id_field("test_id", "1755000000000555") | None = None  # type: ignore[valid-type]
    user_id: id_field("user_id", "1755000000004001") | None = None  # type: ignore[valid-type]
    status: AttemptStatus | None = None
    result: AttemptResult | None = None
    integrity_status: IntegrityStatus | None = None
    plagiarism_flagged: bool | None = None


class GradingQueueQuery(_PagedQuery):
    test_id: id_field("test_id", "1755000000000555") | None = None  # type: ignore[valid-type]
