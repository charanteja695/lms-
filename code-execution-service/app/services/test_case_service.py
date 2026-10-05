from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.crypto import SecretCipher
from app.core.exceptions import BadRequestError, NotFoundError, ValidationFailedError
from app.core.ids import new_public_id
from app.db.session import commit_or_conflict
from app.domain.enums import CompareMode, ProblemStatus, ProblemType
from app.models.problem import Problem
from app.models.test_case import TestCase
from app.schemas.test_case import TestCaseCreate, TestCaseUpdate

MAX_SAMPLES = 10
_ROW_MODES = {CompareMode.ROWS_ORDERED, CompareMode.ROWS_UNORDERED}
_TEMP_POSITION_BASE = 1_000_000  # parks positions out of the way while renumbering (the pair is unique)


def check_compare_mode(problem_type: str, mode: CompareMode | str | None, field: str = "compare_mode") -> None:
    """SQL results are compared as rows; program output as text. The two never mix."""
    if mode is None:
        return
    is_row_mode = CompareMode(mode) in _ROW_MODES
    if (problem_type == ProblemType.SQL) != is_row_mode:
        wanted = "rows_ordered or rows_unordered" if problem_type == ProblemType.SQL else "exact, trim, token or float"
        raise ValidationFailedError(
            details=[{"field": field, "code": "COMPARE_MODE_MISMATCH", "message": f"A {problem_type} problem compares with {wanted}"}]
        )


class TestCaseService:
    __test__ = False  # not a pytest test class, despite the name

    def __init__(self, db: AsyncSession, settings: Settings, cipher: SecretCipher) -> None:
        self.db = db
        self.settings = settings
        self.cipher = cipher

    async def add(self, problem: Problem, data: TestCaseCreate) -> TestCase:
        cases = await self.add_many(problem, [data])
        return cases[0]

    async def add_many(self, problem: Problem, items: list[TestCaseCreate]) -> list[TestCase]:
        self._ensure_draft(problem)
        existing = len(problem.test_cases)
        if existing + len(items) > self.settings.MAX_TEST_CASES_PER_PROBLEM:
            raise BadRequestError(
                f"A problem can have at most {self.settings.MAX_TEST_CASES_PER_PROBLEM} test cases.", code="TOO_MANY_TEST_CASES"
            )
        samples = sum(1 for case in problem.test_cases if case.is_sample) + sum(1 for item in items if item.is_sample)
        if samples > MAX_SAMPLES:
            raise BadRequestError(f"A problem can show at most {MAX_SAMPLES} sample cases.", code="TOO_MANY_SAMPLES")

        next_position = (
            await self.db.execute(select(func.coalesce(func.max(TestCase.position), 0)).where(TestCase.problem_id == problem.id))
        ).scalar_one()
        created: list[TestCase] = []
        for offset, item in enumerate(items, start=1):
            self._validate_content(problem, item.input, item.expected, item.compare_mode, index=offset - 1)
            case = TestCase(
                public_id=new_public_id(),
                problem_id=problem.id,
                position=next_position + offset,
                is_sample=item.is_sample,
                input_encrypted=self.cipher.encrypt(item.input),
                expected_encrypted=self.cipher.encrypt(item.expected),
                compare_mode=item.compare_mode,
                weight=item.weight,
                explanation=item.explanation,
            )
            self.db.add(case)
            created.append(case)
        await commit_or_conflict(self.db)
        return created

    async def get(self, problem: Problem, test_case_id: int) -> TestCase:
        for case in problem.test_cases:
            if case.public_id == test_case_id:
                return case
        raise NotFoundError("Test case not found.", code="TEST_CASE_NOT_FOUND")

    async def update(self, problem: Problem, test_case_id: int, data: TestCaseUpdate) -> TestCase:
        self._ensure_draft(problem)
        case = await self.get(problem, test_case_id)
        fields = data.model_fields_set
        current_input, current_expected = self.decrypt(case)
        new_input = data.input if "input" in fields and data.input is not None else current_input
        new_expected = data.expected if "expected" in fields and data.expected is not None else current_expected
        new_mode = data.compare_mode if "compare_mode" in fields else case.compare_mode
        self._validate_content(problem, new_input, new_expected, new_mode, index=None)

        if "input" in fields and data.input is not None:
            case.input_encrypted = self.cipher.encrypt(new_input)
        if "expected" in fields and data.expected is not None:
            case.expected_encrypted = self.cipher.encrypt(new_expected)
        if "compare_mode" in fields:
            case.compare_mode = data.compare_mode
        if "is_sample" in fields and data.is_sample is not None:
            if data.is_sample and not case.is_sample and sum(1 for c in problem.test_cases if c.is_sample) >= MAX_SAMPLES:
                raise BadRequestError(f"A problem can show at most {MAX_SAMPLES} sample cases.", code="TOO_MANY_SAMPLES")
            case.is_sample = data.is_sample
        if "weight" in fields and data.weight is not None:
            case.weight = data.weight
        if "explanation" in fields:
            case.explanation = data.explanation
        await commit_or_conflict(self.db)
        return case

    async def delete(self, problem: Problem, test_case_id: int) -> None:
        self._ensure_draft(problem)
        case = await self.get(problem, test_case_id)
        await self.db.delete(case)
        await self.db.flush()
        remaining = [c for c in problem.test_cases if c.id != case.id]
        await self._renumber(remaining)
        await self.db.commit()

    async def reorder(self, problem: Problem, ordered_ids: list[int]) -> list[TestCase]:
        self._ensure_draft(problem)
        by_id = {case.public_id: case for case in problem.test_cases}
        if len(ordered_ids) != len(by_id) or set(ordered_ids) != set(by_id):
            raise ValidationFailedError(
                details=[{"field": "test_case_ids", "code": "NOT_ALL_TEST_CASES", "message": "List every test case of the problem exactly once"}]
            )
        ordered = [by_id[test_case_id] for test_case_id in ordered_ids]
        await self._renumber(ordered)
        await self.db.commit()
        return ordered

    def decrypt(self, case: TestCase) -> tuple[str, str]:
        return self.cipher.decrypt(case.input_encrypted), self.cipher.decrypt(case.expected_encrypted)

    # ------------------------------------------------------------------ internals

    async def _renumber(self, ordered: list[TestCase]) -> None:
        for index, case in enumerate(ordered):
            case.position = _TEMP_POSITION_BASE + index
        await self.db.flush()
        for index, case in enumerate(ordered, start=1):
            case.position = index
        await self.db.flush()

    @staticmethod
    def _ensure_draft(problem: Problem) -> None:
        if problem.status != ProblemStatus.DRAFT:
            raise BadRequestError("A published problem's test cases are frozen.", code="PROBLEM_NOT_DRAFT")

    def _validate_content(self, problem: Problem, test_input: str, expected: str, mode: CompareMode | str | None, *, index: int | None) -> None:
        prefix = f"test_cases[{index}]." if index is not None else ""
        limit = self.settings.MAX_TEST_CASE_BYTES
        details = []
        if len(test_input.encode()) > limit:
            details.append({"field": f"{prefix}input", "code": "TOO_LARGE", "message": f"At most {limit} bytes"})
        if len(expected.encode()) > limit:
            details.append({"field": f"{prefix}expected", "code": "TOO_LARGE", "message": f"At most {limit} bytes"})
        if details:
            raise ValidationFailedError(details=details)
        check_compare_mode(problem.problem_type, mode, f"{prefix}compare_mode")
