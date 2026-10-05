from fastapi import APIRouter, Response

from app.api.deps import (
    AuthoringRateLimit,
    CipherDep,
    DbSession,
    ProblemIdParam,
    RequireAuthor,
    RequireReviewer,
    SettingsDep,
    TestCaseIdParam,
)
from app.api.responses import errors
from app.models.test_case import TestCase
from app.schemas.test_case import (
    TestCaseBulkCreate,
    TestCaseCreate,
    TestCaseListResponse,
    TestCaseOut,
    TestCaseReorder,
    TestCaseResponse,
    TestCaseUpdate,
)
from app.services.problem_service import ProblemService
from app.services.test_case_service import TestCaseService

router = APIRouter(prefix="/problems/{problem_id}/test-cases", tags=["Test cases"])


def _out(service: TestCaseService, case: TestCase) -> TestCaseOut:
    """The decrypted case, for authors and reviewers only."""
    test_input, expected = service.decrypt(case)
    return TestCaseOut(
        test_case_id=case.public_id,
        position=case.position,
        is_sample=case.is_sample,
        input=test_input,
        expected=expected,
        compare_mode=case.compare_mode,
        weight=case.weight,
        explanation=case.explanation,
        created_at=case.created_at,
    )


@router.get("", response_model=TestCaseListResponse, summary="List a problem's test cases, hidden ones included", responses=errors(401, 403, 404, 429))
async def list_test_cases(problem_id: ProblemIdParam, auth: RequireReviewer, db: DbSession, settings: SettingsDep, cipher: CipherDep) -> TestCaseListResponse:
    problem = await ProblemService(db, settings, cipher).get(problem_id)
    service = TestCaseService(db, settings, cipher)
    return TestCaseListResponse(message="Test cases retrieved successfully.", test_cases=[_out(service, case) for case in problem.test_cases])


@router.post(
    "",
    response_model=TestCaseResponse,
    status_code=201,
    summary="Add a test case to a draft problem",
    responses=errors(400, 401, 403, 404, 422, 429),
    dependencies=[AuthoringRateLimit],
)
async def add_test_case(problem_id: ProblemIdParam, data: TestCaseCreate, auth: RequireAuthor, db: DbSession, settings: SettingsDep, cipher: CipherDep) -> TestCaseResponse:
    problem = await ProblemService(db, settings, cipher).get(problem_id)
    service = TestCaseService(db, settings, cipher)
    return TestCaseResponse(message="Test case added successfully.", test_case=_out(service, await service.add(problem, data)))


@router.post(
    "/bulk",
    response_model=TestCaseListResponse,
    status_code=201,
    summary="Add up to 200 test cases at once",
    responses=errors(400, 401, 403, 404, 422, 429),
    dependencies=[AuthoringRateLimit],
)
async def add_test_cases(problem_id: ProblemIdParam, data: TestCaseBulkCreate, auth: RequireAuthor, db: DbSession, settings: SettingsDep, cipher: CipherDep) -> TestCaseListResponse:
    problem = await ProblemService(db, settings, cipher).get(problem_id)
    service = TestCaseService(db, settings, cipher)
    created = await service.add_many(problem, data.test_cases)
    return TestCaseListResponse(message="Test cases added successfully.", test_cases=[_out(service, case) for case in created])


@router.post(
    "/reorder",
    response_model=TestCaseListResponse,
    summary="Set the order of the test cases",
    responses=errors(400, 401, 403, 404, 422, 429),
    dependencies=[AuthoringRateLimit],
)
async def reorder_test_cases(problem_id: ProblemIdParam, data: TestCaseReorder, auth: RequireAuthor, db: DbSession, settings: SettingsDep, cipher: CipherDep) -> TestCaseListResponse:
    problem = await ProblemService(db, settings, cipher).get(problem_id)
    service = TestCaseService(db, settings, cipher)
    ordered = await service.reorder(problem, data.test_case_ids)
    return TestCaseListResponse(message="Test cases reordered successfully.", test_cases=[_out(service, case) for case in ordered])


@router.patch(
    "/{test_case_id}",
    response_model=TestCaseResponse,
    summary="Edit a test case of a draft problem",
    responses=errors(400, 401, 403, 404, 422, 429),
    dependencies=[AuthoringRateLimit],
)
async def update_test_case(problem_id: ProblemIdParam, test_case_id: TestCaseIdParam, data: TestCaseUpdate, auth: RequireAuthor, db: DbSession, settings: SettingsDep, cipher: CipherDep) -> TestCaseResponse:
    problem = await ProblemService(db, settings, cipher).get(problem_id)
    service = TestCaseService(db, settings, cipher)
    return TestCaseResponse(message="Test case updated successfully.", test_case=_out(service, await service.update(problem, test_case_id, data)))


@router.delete(
    "/{test_case_id}",
    status_code=204,
    summary="Delete a test case of a draft problem",
    responses=errors(400, 401, 403, 404, 429),
    dependencies=[AuthoringRateLimit],
)
async def delete_test_case(problem_id: ProblemIdParam, test_case_id: TestCaseIdParam, auth: RequireAuthor, db: DbSession, settings: SettingsDep, cipher: CipherDep) -> Response:
    problem = await ProblemService(db, settings, cipher).get(problem_id)
    await TestCaseService(db, settings, cipher).delete(problem, test_case_id)
    return Response(status_code=204)
