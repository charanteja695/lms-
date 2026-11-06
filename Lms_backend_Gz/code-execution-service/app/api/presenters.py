"""Maps domain objects to response schemas. Kept out of the endpoints so they stay thin, and free of
rules: everything decided here is presentation (what a student may see), never business logic."""

from app.models.language import Language
from app.models.problem import Problem
from app.schemas.problem import ProblemAuthorOut, ProblemListItem, ProblemOut
from app.schemas.test_case import SampleCaseOut
from app.services.problem_service import allowed_language_codes
from app.services.test_case_service import TestCaseService


def problem_list_item(problem: Problem, *, solved: set[int], attempted: set[int]) -> ProblemListItem:
    item = ProblemListItem.model_validate(problem)
    item.solved = problem.public_id in solved
    item.attempted = problem.public_id in attempted
    return item


def _samples(problem: Problem, cases: TestCaseService) -> list[SampleCaseOut]:
    samples = []
    for case in problem.test_cases:
        if case.is_sample:
            test_input, expected = cases.decrypt(case)
            samples.append(SampleCaseOut(position=case.position, input=test_input, expected=expected, explanation=case.explanation))
    return samples


def problem_out(
    problem: Problem, cases: TestCaseService, enabled: list[Language], *, solved: set[int], attempted: set[int]
) -> ProblemOut:
    """What a student sees: the statement, limits, usable languages and the sample cases. Hidden cases never."""
    base = problem_list_item(problem, solved=solved, attempted=attempted)
    return ProblemOut(
        **base.model_dump(),
        statement=problem.statement,
        time_limit_ms=problem.time_limit_ms,
        memory_limit_mb=problem.memory_limit_mb,
        allowed_languages=sorted(allowed_language_codes(problem, enabled)),
        samples=_samples(problem, cases),
        created_at=problem.created_at,
        published_at=problem.published_at,
    )


def problem_author_out(
    problem: Problem, cases: TestCaseService, enabled: list[Language], *, solved: set[int], attempted: set[int]
) -> ProblemAuthorOut:
    student_view = problem_out(problem, cases, enabled, solved=solved, attempted=attempted)
    return ProblemAuthorOut(
        **student_view.model_dump(),
        configured_languages=list(problem.allowed_languages),
        compare_mode=problem.compare_mode,
        float_tolerance=problem.float_tolerance,
        has_setup_sql=problem.setup_sql_encrypted is not None,
        test_case_count=len(problem.test_cases),
        created_by=problem.created_by,
    )
