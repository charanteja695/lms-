from fastapi import APIRouter

from app.api.deps import (
    CurrentAuth,
    DbSession,
    EnrollmentIdParam,
    SettingsDep,
    TopicItemIdParam,
    ensure_organization_visible,
)
from app.api.responses import errors
from app.core.exceptions import PermissionDeniedError
from app.schemas.progress import ItemProgressOut, ItemProgressResponse, UnlockStateOut, UnlockStateResponse
from app.services.enrollment_service import EnrollmentService
from app.services.progress_service import ProgressService

router = APIRouter(prefix="/enrollments/{enrollment_id}", tags=["Progress"])


@router.post(
    "/items/{topic_item_id}/complete",
    response_model=ItemProgressResponse,
    status_code=201,
    summary="Mark a topic item complete",
    description="Only the enrolled student may mark their own progress. Idempotent.",
    responses=errors(400, 401, 403, 404),
)
async def complete_item(
    enrollment_id: EnrollmentIdParam, topic_item_id: TopicItemIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep
) -> ItemProgressResponse:
    enrollment = await EnrollmentService(db, settings).get(enrollment_id)
    if auth.user_id != enrollment.student_user_id:
        raise PermissionDeniedError()
    progress = await ProgressService(db).complete_item(enrollment, topic_item_id)
    return ItemProgressResponse(message="Item marked complete.", item_progress=ItemProgressOut.model_validate(progress))


@router.get(
    "/unlock-state",
    response_model=UnlockStateResponse,
    summary="Get module/topic unlock and completion state",
    responses=errors(401, 403, 404),
)
async def get_unlock_state(enrollment_id: EnrollmentIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> UnlockStateResponse:
    enrollment = await EnrollmentService(db, settings).get(enrollment_id)
    if auth.user_id != enrollment.student_user_id:
        ensure_organization_visible(auth, enrollment.batch.organization_id)
    state = await ProgressService(db).unlock_state(enrollment)
    return UnlockStateResponse(message="Unlock state retrieved successfully.", unlock_state=UnlockStateOut.model_validate(state))
