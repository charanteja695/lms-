from typing import Annotated, Any

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder
from lms_common.pagination import paginate
from sqlalchemy import func, or_, select

from app.api.deps import CurrentAuth, DbSession, RequireStudent, SettingsDep, TestIdParam
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import NotFoundError
from app.domain.enums import AttemptResult, TestStatus
from app.models.attempt import Attempt
from app.models.test import Test
from app.schemas.attempt import MyTestOut, MyTestResponse, MyTestsResponse
from app.schemas.common import MyTestsQuery
from app.services.eligibility_service import EligibilityService
from app.services.test_service import TestService

router = APIRouter(prefix="/my/tests", tags=["My tests"])


async def _describe(service: EligibilityService, test: Test, auth: CurrentAuth) -> MyTestOut:
    eligibility = await service.check(test, auth)
    open_attempt = await service.open_attempt(test, auth.user_id)
    best = (
        await service.db.execute(
            select(func.max(Attempt.percent)).where(
                Attempt.user_id == auth.user_id,
                Attempt.test_id == test.id,
                Attempt.results_visible_at.is_not(None),
                Attempt.result != AttemptResult.INVALIDATED,
            )
        )
    ).scalar_one()
    return MyTestOut(
        test_id=test.public_id,
        title=test.title,
        kind=test.kind,
        description=test.description,
        time_mode=test.time_mode,
        duration_minutes=test.duration_minutes,
        pass_mark_percent=test.pass_mark_percent,
        question_count=test.question_count,
        total_marks=test.total_marks,
        proctoring_level=test.proctoring_level,
        can_start=eligibility.can_start or open_attempt is not None,
        reason=None if open_attempt is not None else eligibility.reason,
        message=None if open_attempt is not None else eligibility.message,
        attempts_used=eligibility.attempts_used,
        attempts_left=eligibility.attempts_left,
        next_available_at=eligibility.next_available_at,
        opens_at=eligibility.opens_at,
        open_attempt_id=open_attempt.public_id if open_attempt else None,
        best_percent=float(best) if best is not None else None,
    )


@router.get(
    "",
    response_model=MyTestsResponse,
    summary="Tests I can take",
    description="Published tests open to this student — from their enrolments, practice tests and hiring invitations — "
    "each with whether they can start now and, if not, why (`reason`), attempts left, cooldown and exam start time.",
    responses=errors(*AUTHENTICATED),
)
async def my_tests(query: Annotated[MyTestsQuery, Query()], auth: RequireStudent, db: DbSession, settings: SettingsDep) -> MyTestsResponse:
    eligibility = EligibilityService(db, settings)
    stmt = select(Test).where(Test.status == TestStatus.PUBLISHED, or_(*await eligibility.available_tests_filter(auth.user_id)))
    if query.kind:
        stmt = stmt.where(Test.kind == query.kind)
    if query.target_id:
        stmt = stmt.where(Test.target_id == query.target_id)
    stmt = stmt.order_by(Test.created_at.asc() if query.sort_order == "asc" else Test.created_at.desc(), Test.id)
    tests, total, is_exact = await paginate(db, stmt, query.page, query.per_page)
    return MyTestsResponse(
        message="Tests retrieved successfully.",
        tests=[await _describe(eligibility, test, auth) for test in tests],
        page_context=PageContext.build(
            page=query.page, per_page=query.per_page, total=total, is_exact=is_exact,
            sort_column="created_time", sort_order=SortOrder(query.sort_order),
        ),
    )


@router.get(
    "/{test_id}",
    response_model=MyTestResponse,
    summary="A test as a student sees it before starting",
    description="Rules, instructions and section outline: never the questions or answer keys.",
    responses=errors(*AUTHENTICATED, 404),
)
async def my_test(test_id: TestIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> MyTestResponse:
    test = await TestService(db, settings).load(test_id)
    eligibility = EligibilityService(db, settings)
    described = await _describe(eligibility, test, auth)
    if test.status != TestStatus.PUBLISHED or described.reason in {"NOT_ENROLLED", "NOT_INVITED", "TEST_NOT_AVAILABLE"}:
        raise NotFoundError("Test not found.", code="TEST_NOT_FOUND")
    sections: list[dict[str, Any]] = [
        {"section_id": str(s.public_id), "position": s.position, "title": s.title, "instructions": s.instructions, "time_limit_minutes": s.time_limit_minutes}
        for s in test.sections
    ]
    return MyTestResponse(message="Test retrieved successfully.", test=described, instructions=test.instructions, sections=sections)
