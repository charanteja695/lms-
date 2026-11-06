from typing import Annotated

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import AfterValidator, AliasChoices, Field

from app.domain.enums import CompareMode, Difficulty, ProblemType
from app.schemas.test_case import SampleCaseOut
from app.schemas.types import PublicIdOut, Timestamp, multiline_text, raw_text, text

ProblemTitle = text(200, min_length=3, examples=["Sum of two numbers"])
Statement = multiline_text(50_000, examples=["Read two integers and print their sum."])
SetupSql = raw_text(200_000)
LanguageCodeItem = text(30)


def _tag(value: str) -> str:
    value = value.strip().lower()
    if not value or len(value) > 30 or not all(char.isalnum() or char in "-_ " for char in value):
        raise ValueError("Tags are 1-30 letters, digits, spaces, hyphens or underscores")
    return value


Tag = Annotated[str, AfterValidator(_tag)]


class ProblemCreate(RequestSchema):
    title: ProblemTitle  # type: ignore[valid-type]
    statement: Statement  # type: ignore[valid-type]
    problem_type: ProblemType = ProblemType.CODE
    difficulty: Difficulty = Difficulty.EASY
    tags: list[Tag] = Field(default_factory=list, max_length=10)
    time_limit_ms: int = Field(default=2_000, ge=100)
    memory_limit_mb: int = Field(default=256, ge=16)
    allowed_languages: list[LanguageCodeItem] = Field(  # type: ignore[valid-type]
        default_factory=list, max_length=40, description="Empty: every enabled language of the problem's type"
    )
    setup_sql: SetupSql | None = Field(default=None, description="SQL problems: schema and seed data. Never shown")  # type: ignore[valid-type]
    compare_mode: CompareMode = CompareMode.TRIM
    float_tolerance: float = Field(default=1e-6, gt=0, le=1)


class ProblemUpdate(RequestSchema):
    """Partial update of a draft."""

    title: ProblemTitle | None = None  # type: ignore[valid-type]
    statement: Statement | None = None  # type: ignore[valid-type]
    difficulty: Difficulty | None = None
    tags: list[Tag] | None = Field(default=None, max_length=10)
    time_limit_ms: int | None = Field(default=None, ge=100)
    memory_limit_mb: int | None = Field(default=None, ge=16)
    allowed_languages: list[LanguageCodeItem] | None = Field(default=None, max_length=40)  # type: ignore[valid-type]
    setup_sql: SetupSql | None = None  # type: ignore[valid-type]
    compare_mode: CompareMode | None = None
    float_tolerance: float | None = Field(default=None, gt=0, le=1)


class ProblemListItem(ResponseSchema):
    # Read from the ORM object (public_id) or from another ProblemListItem dumped to a dict (problem_id).
    problem_id: PublicIdOut = Field(validation_alias=AliasChoices("public_id", "problem_id"))
    title: str
    problem_type: str
    difficulty: str
    tags: list[str]
    status: str
    solved: bool = Field(default=False, description="This user has an accepted submission")
    attempted: bool = Field(default=False, description="This user has submitted at least once")


class ProblemOut(ProblemListItem):
    statement: str
    time_limit_ms: int
    memory_limit_mb: int
    allowed_languages: list[str] = Field(description="Languages a student may use right now")
    samples: list[SampleCaseOut]
    created_at: Timestamp
    published_at: Timestamp | None


class ProblemAuthorOut(ProblemOut):
    """Authors and reviewers: adds what students never see."""

    configured_languages: list[str] = Field(description="What the author set; empty means every enabled language")
    compare_mode: str
    float_tolerance: float
    has_setup_sql: bool
    test_case_count: int
    created_by: PublicIdOut


class ProblemResponse(SuccessResponse):
    problem: ProblemOut


class ProblemAuthorResponse(SuccessResponse):
    problem: ProblemAuthorOut


class ProblemListResponse(SuccessResponse):
    problems: list[ProblemListItem]
    page_context: PageContext


class ProblemStatsOut(ResponseSchema):
    submissions: int
    accepted: int
    acceptance_percent: int
    solvers: int = Field(description="Distinct users with an accepted submission")
    flagged: int = Field(description="Submissions flagged as similar to another")
    verdicts: dict[str, int]


class ProblemStatsResponse(SuccessResponse):
    stats: ProblemStatsOut
