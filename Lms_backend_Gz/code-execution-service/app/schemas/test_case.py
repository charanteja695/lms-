from lms_common.envelopes import RequestSchema, ResponseSchema, SuccessResponse
from pydantic import AliasChoices, Field

from app.domain.enums import CompareMode
from app.schemas.types import PublicIdOut, Timestamp, id_field, raw_text

# Exact text: whitespace and the final newline are part of a test case. Bytes are checked against
# Settings.MAX_TEST_CASE_BYTES in the service.
CaseText = raw_text(2_000_000)
Explanation = raw_text(5_000)
TestCaseId = id_field("test_case_id", "1755000000006777")


class TestCaseCreate(RequestSchema):
    __test__ = False

    input: CaseText = Field(default="", description="Programs: stdin. SQL: extra seed data run after the problem's setup script")  # type: ignore[valid-type]
    expected: CaseText  # type: ignore[valid-type]
    is_sample: bool = Field(default=False, description="Shown to students in the problem; hidden cases never are")
    compare_mode: CompareMode | None = Field(default=None, description="Overrides the problem's compare mode")
    weight: int = Field(default=1, ge=1, le=100)
    explanation: Explanation | None = None  # type: ignore[valid-type]


class TestCaseUpdate(RequestSchema):
    __test__ = False

    input: CaseText | None = None  # type: ignore[valid-type]
    expected: CaseText | None = None  # type: ignore[valid-type]
    is_sample: bool | None = None
    compare_mode: CompareMode | None = None
    weight: int | None = Field(default=None, ge=1, le=100)
    explanation: Explanation | None = None  # type: ignore[valid-type]


class TestCaseBulkCreate(RequestSchema):
    __test__ = False

    test_cases: list[TestCaseCreate] = Field(min_length=1, max_length=200)


class TestCaseReorder(RequestSchema):
    __test__ = False

    test_case_ids: list[TestCaseId] = Field(min_length=1, max_length=500, description="Every test case, in the new order")  # type: ignore[valid-type]


class TestCaseOut(ResponseSchema):
    """Authors only: decrypted, including hidden cases."""

    __test__ = False

    test_case_id: PublicIdOut = Field(validation_alias=AliasChoices("public_id", "test_case_id"))
    position: int
    is_sample: bool
    input: str
    expected: str
    compare_mode: str | None
    weight: int
    explanation: str | None
    created_at: Timestamp


class TestCaseResponse(SuccessResponse):
    __test__ = False

    test_case: TestCaseOut


class TestCaseListResponse(SuccessResponse):
    __test__ = False

    test_cases: list[TestCaseOut]


class SampleCaseOut(ResponseSchema):
    """What a student sees of a sample case."""

    position: int
    input: str
    expected: str
    explanation: str | None
