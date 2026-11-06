from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import (
    CipherDep,
    CurrentAuth,
    DbSession,
    IdempotencyKeyHeader,
    ProblemIdParam,
    RateLimiterDep,
    RequireOwnSubmissions,
    RequirePractice,
    SettingsDep,
    SubmissionIdParam,
)
from app.api.responses import AUTHENTICATED, errors
from app.domain.enums import JobStatus, Priority
from app.schemas.common import SubmissionQuery
from app.schemas.submission import (
    SubmissionCreate,
    SubmissionListItem,
    SubmissionListResponse,
    SubmissionOut,
    SubmissionResponse,
)
from app.services.problem_service import ProblemService
from app.services.submission_service import SubmissionService

router = APIRouter(tags=["Submissions"])


@router.post(
    "/problems/{problem_id}/submissions",
    response_model=SubmissionResponse,
    status_code=202,
    summary="Submit a solution",
    description="Queues the solution to be judged against every test case, hidden ones included, and returns at once. "
    "Read the verdict with GET /submissions/{id} (optionally waiting). Send an Idempotency-Key so a retry does not "
    "judge the same code twice.",
    responses=errors(401, 404, 422, 429),
)
async def submit(
    problem_id: ProblemIdParam,
    data: SubmissionCreate,
    auth: RequirePractice,
    db: DbSession,
    settings: SettingsDep,
    cipher: CipherDep,
    limiter: RateLimiterDep,
    key: IdempotencyKeyHeader,
) -> SubmissionResponse:
    problem = await ProblemService(db, settings, cipher).get_visible(problem_id, is_reviewer=False)
    submission = await SubmissionService(db, settings, limiter).create(
        user_id=auth.user_id,
        organization_id=auth.organization_id,
        problem=problem,
        language_code=data.language,
        source=data.source,
        priority=Priority.SUBMISSION,
        key=key,
    )
    return SubmissionResponse(message="Submission queued.", submission=SubmissionOut.model_validate(submission))


@router.get("/submissions", response_model=SubmissionListResponse, summary="List my submissions", responses=errors(*AUTHENTICATED))
async def list_my_submissions(
    query: Annotated[SubmissionQuery, Query()], auth: RequireOwnSubmissions, db: DbSession, settings: SettingsDep
) -> SubmissionListResponse:
    submissions, total, is_exact = await SubmissionService(db, settings).list_submissions(query, user_id=auth.user_id)
    return SubmissionListResponse(
        message="Submissions retrieved successfully.",
        submissions=[SubmissionListItem.model_validate(submission) for submission in submissions],
        page_context=PageContext.build(
            page=query.page, per_page=query.per_page, total=total, is_exact=is_exact,
            sort_column="created_time", sort_order=SortOrder(query.sort_order),
        ),
    )


@router.get(
    "/submissions/{submission_id}",
    response_model=SubmissionResponse,
    summary="Get one of my submissions",
    description="`wait` (seconds) holds the request open until judging finishes. Sample cases show their input, the "
    "expected output and yours; hidden cases show the verdict only.",
    responses=errors(401, 404, 429),
)
async def get_my_submission(
    submission_id: SubmissionIdParam,
    auth: CurrentAuth,
    db: DbSession,
    settings: SettingsDep,
    wait: Annotated[float, Query(ge=0, le=30)] = 0,
) -> SubmissionResponse:
    service = SubmissionService(db, settings)
    submission = await service.get_visible(submission_id, user_id=auth.user_id, is_reviewer=False)
    if wait and submission.status != JobStatus.COMPLETED:
        submission = await service.wait_until_done(submission, wait)
    return SubmissionResponse(message="Submission retrieved successfully.", submission=SubmissionOut.model_validate(submission))

