"""Endpoints for other services, not people: authenticated with the shared internal service token
(``X-Internal-Service-Token``), not a user's access token — same scheme as subscription-service's seat calls.

  proctoring-service   pause / unpause / terminate a live attempt, and report an integrity decision
  job-portal-service   invite a candidate to a hiring assessment
"""

from fastapi import APIRouter

from app.api.deps import AttemptIdParam, DbSession, InternalCaller, RedisDep, SettingsDep
from app.api.responses import errors
from app.api.views import state_of
from app.core.exceptions import NotFoundError
from app.schemas.attempt import AttemptResponse, IntegrityDecisionIn, QueueOut, QueueResponse, ReasonIn
from app.schemas.test import AssignmentCreate, AssignmentOut, AssignmentResponse
from app.services.answer_buffer import AnswerBuffer
from app.services.attempt_service import AttemptService
from app.services.grading_service import GradingService
from app.services.result_service import ResultService
from app.services.schedule_service import ScheduleService

router = APIRouter(prefix="/internal", tags=["Internal"], dependencies=[InternalCaller])

_ACTOR = 0  # the calling service acts, not a person


@router.post(
    "/assignments",
    response_model=AssignmentResponse,
    status_code=201,
    summary="Invite a candidate to a hiring assessment (job-portal-service)",
    description="Creates or updates the invitation; the candidate then finds the test in GET /my/tests.",
    responses=errors(401, 403, 404, 409, 422),
)
async def invite_candidate(data: AssignmentCreate, db: DbSession) -> AssignmentResponse:
    assignment, test = await ScheduleService(db).invite(data)
    return AssignmentResponse(
        message="Candidate invited.",
        assignment=AssignmentOut(
            test_id=test.public_id,
            user_id=assignment.user_id,
            reference=assignment.reference,
            opens_at=assignment.opens_at,
            expires_at=assignment.expires_at,
            max_attempts=assignment.max_attempts,
        ),
    )


@router.post("/attempts/{attempt_id}/pause", response_model=AttemptResponse, summary="Pause a live attempt (proctoring-service)", responses=errors(401, 403, 404, 409))
async def pause(attempt_id: AttemptIdParam, data: ReasonIn, db: DbSession, settings: SettingsDep, redis: RedisDep) -> AttemptResponse:
    service = AttemptService(db, settings, redis)
    attempt = await service.pause(await service.get(attempt_id), _ACTOR, data.reason)
    return AttemptResponse(message="Attempt paused.", attempt=await state_of(service, attempt))


@router.post("/attempts/{attempt_id}/unpause", response_model=AttemptResponse, summary="Resume a paused attempt (proctoring-service)", responses=errors(401, 403, 404, 409))
async def unpause(attempt_id: AttemptIdParam, db: DbSession, settings: SettingsDep, redis: RedisDep) -> AttemptResponse:
    service = AttemptService(db, settings, redis)
    attempt = await service.unpause(await service.get(attempt_id), _ACTOR)
    return AttemptResponse(message="Attempt resumed.", attempt=await state_of(service, attempt))


@router.post("/attempts/{attempt_id}/terminate", response_model=AttemptResponse, summary="Terminate a live attempt (proctoring-service)", responses=errors(401, 403, 404, 409))
async def terminate(attempt_id: AttemptIdParam, data: ReasonIn, db: DbSession, settings: SettingsDep, redis: RedisDep) -> AttemptResponse:
    service = AttemptService(db, settings, redis)
    attempt = await service.terminate(await service.get(attempt_id), _ACTOR, data.reason)
    return AttemptResponse(message="Attempt terminated.", attempt=await state_of(service, attempt))


@router.post(
    "/attempts/{attempt_id}/integrity",
    response_model=AttemptResponse,
    summary="Record an integrity decision (proctoring-service)",
    description="The synchronous twin of the `integrity.decided` event (`clear`, `reviewed_ok`, `invalidated`). A human "
    "confirms every invalidation in proctoring-service; this service only applies the decision.",
    responses=errors(401, 403, 404, 422),
)
async def integrity(attempt_id: AttemptIdParam, data: IntegrityDecisionIn, db: DbSession, settings: SettingsDep, redis: RedisDep) -> AttemptResponse:
    service = AttemptService(db, settings, redis)
    await service.get(attempt_id)  # 404 for an unknown attempt
    await ResultService(db, settings, redis).integrity_decided(attempt_id, data.decision)
    return AttemptResponse(message="Integrity decision applied.", attempt=await state_of(service, await service.get(attempt_id)))


@router.get("/queue", response_model=QueueResponse, summary="Work waiting for the workers (autoscaling signal)", responses=errors(401, 403))
async def queue(db: DbSession, settings: SettingsDep, redis: RedisDep) -> QueueResponse:
    from sqlalchemy import func, select

    from app.domain.enums import CodingStatus
    from app.models.attempt import CodingSubmission

    coding = {
        status: int(count)
        for status, count in (
            await db.execute(select(CodingSubmission.status, func.count()).where(CodingSubmission.status.in_([CodingStatus.PENDING, CodingStatus.DISPATCHED])).group_by(CodingSubmission.status))
        ).all()
    }
    return QueueResponse(
        message="Queue depth retrieved successfully.",
        queue=QueueOut(
            grading=await GradingService(db, settings, redis).queue_depth(),
            coding=coding,
            answers_waiting_to_flush=await AnswerBuffer(redis, settings).dirty_count(),
        ),
    )


__all__ = ["NotFoundError", "router"]
