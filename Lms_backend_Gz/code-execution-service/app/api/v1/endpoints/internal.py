"""Endpoints for other services, not people: authenticated with the shared internal service token
(``X-Internal-Service-Token``), not a user's access token — same scheme as subscription-service's seat calls."""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import ResponseSchema, SuccessResponse

from app.api.deps import (
    CipherDep,
    DbSession,
    IdempotencyKeyHeader,
    InternalCaller,
    RunIdParam,
    SettingsDep,
    SubmissionIdParam,
)
from app.api.responses import errors
from app.domain.enums import JobStatus
from app.models.run import Run
from app.models.submission import Submission
from app.schemas.run import InternalRunCreate, RunOut, RunResponse
from app.schemas.submission import InternalSubmissionCreate, ReviewSubmissionOut, ReviewSubmissionResponse
from app.services.problem_service import ProblemService
from app.services.queue_service import QueueService
from app.services.run_service import RunService
from app.services.submission_service import SubmissionService

router = APIRouter(prefix="/internal", tags=["Internal"], dependencies=[InternalCaller])


@router.post(
    "/submissions",
    response_model=ReviewSubmissionResponse,
    status_code=202,
    summary="Submit a solution on a student's behalf (assessment-service)",
    description="Queued in the exam lane by default, ahead of all practice work. The verdict is published as a "
    "`submission.judged` event carrying `reference`; it can also be read from GET /internal/submissions/{id}.",
    responses=errors(401, 403, 404, 422),
)
async def submit_for_student(
    data: InternalSubmissionCreate, db: DbSession, settings: SettingsDep, cipher: CipherDep, key: IdempotencyKeyHeader
) -> ReviewSubmissionResponse:
    problem = await ProblemService(db, settings, cipher).get_visible(data.problem_id, is_reviewer=False)
    submission = await SubmissionService(db, settings).create(  # no limiter: the caller paces its own students
        user_id=data.user_id,
        organization_id=data.organization_id,
        problem=problem,
        language_code=data.language,
        source=data.source,
        priority=data.priority,
        reference=data.reference,
        key=key,
    )
    return ReviewSubmissionResponse(message="Submission queued.", submission=ReviewSubmissionOut.model_validate(submission))


@router.get(
    "/submissions/{submission_id}",
    response_model=ReviewSubmissionResponse,
    summary="Read a submission (assessment-service)",
    responses=errors(401, 403, 404),
)
async def get_submission(submission_id: SubmissionIdParam, db: DbSession, settings: SettingsDep) -> ReviewSubmissionResponse:
    submission = await SubmissionService(db, settings).get(submission_id)
    return ReviewSubmissionResponse(message="Submission retrieved successfully.", submission=ReviewSubmissionOut.model_validate(submission))


class QueueDepthOut(ResponseSchema):
    runs: dict[int, int]
    submissions: dict[int, int]


class QueueDepthResponse(SuccessResponse):
    queue: QueueDepthOut


@router.get(
    "/queue",
    response_model=QueueDepthResponse,
    summary="Jobs waiting per lane (0 practice, 1 submission, 2 exam)",
    description="The autoscaling signal for the worker pool: scale on the depth of the lanes, most importantly 2.",
    responses=errors(401, 403),
)
async def queue_depth(db: DbSession, settings: SettingsDep) -> QueueDepthResponse:
    queue = QueueService(db, settings)
    return QueueDepthResponse(
        message="Queue depth retrieved successfully.",
        queue=QueueDepthOut(runs=await queue.depth(Run), submissions=await queue.depth(Submission)),
    )


@router.post(
    "/runs",
    response_model=RunResponse,
    status_code=202,
    summary="Run code on a person's behalf (ai-interview-service)",
    description="The coding round of an AI interview: the candidate's code is run in the practice lane exactly as if they had pressed Run. Read the result with GET /internal/runs/{id}.",
    responses=errors(401, 403, 404, 422),
)
async def run_for_person(data: InternalRunCreate, db: DbSession, settings: SettingsDep) -> RunResponse:
    run = await RunService(db, settings).create_for_service(
        user_id=data.user_id, organization_id=data.organization_id, language=data.language, source=data.source, stdin=data.stdin
    )
    return RunResponse(message="Run queued.", run=RunOut.model_validate(run))


@router.get("/runs/{run_id}", response_model=RunResponse, summary="Read a run (ai-interview-service)", responses=errors(401, 403, 404))
async def read_run(run_id: RunIdParam, db: DbSession, settings: SettingsDep, wait: Annotated[float, Query(ge=0, le=30)] = 0) -> RunResponse:
    service = RunService(db, settings)
    run = await service.get(run_id)
    if wait and run.status != JobStatus.COMPLETED:
        run = await service.wait_until_done(run, wait)
    return RunResponse(message="Run retrieved successfully.", run=RunOut.model_validate(run))
