from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import (
    STUDY,
    BatchIdParam,
    CurrentAuth,
    DbSession,
    EnrollmentIdParam,
    RedisDep,
    RequireBatchCreate,
    RequireBatchRevoke,
    SettingsDep,
    ensure_organization_visible,
    institutions_in_care,
    sees_all_institutions,
    sees_own_batches,
)
from app.api.responses import errors
from app.core.exceptions import PermissionDeniedError
from app.core.ids import parse_public_id
from app.core.security import AccessTokenClaims
from app.models.enrollment import Enrollment
from app.schemas.enrollment import (
    EnrollmentCreate,
    EnrollmentListQuery,
    EnrollmentListResponse,
    EnrollmentOut,
    EnrollmentResponse,
)
from app.services.batch_service import BatchService
from app.services.enrollment_service import EnrollmentService

router = APIRouter(tags=["Enrollments"])


def _ensure_enrollment_visible(auth: AccessTokenClaims, enrollment: Enrollment) -> None:
    if auth.user_id == enrollment.student_user_id:
        return
    ensure_organization_visible(auth, enrollment.batch.organization_id)


@router.post(
    "/batches/{batch_id}/enrollments",
    response_model=EnrollmentResponse,
    status_code=201,
    summary="Enrol a student in a batch",
    description="Reserves a seat on the batch's subscription (see subscription-service) before creating the enrolment.",
    responses=errors(400, 401, 403, 404, 409, 422),
)
async def create_enrollment(
    batch_id: BatchIdParam, data: EnrollmentCreate, auth: RequireBatchCreate, db: DbSession, settings: SettingsDep, redis: RedisDep
) -> EnrollmentResponse:
    batch = await BatchService(db, settings, redis).get(batch_id)
    ensure_organization_visible(auth, batch.organization_id)

    enrollment = await EnrollmentService(db, settings).enroll(batch, data.student_user_id)
    return EnrollmentResponse(message="Student enrolled successfully.", enrollment=EnrollmentOut.model_validate(enrollment))


@router.get(
    "/enrollments",
    response_model=EnrollmentListResponse,
    summary="List enrollments",
    description="A student sees only their own enrolments. An institution head sees their institution's "
    "(optionally narrowed to one batch); accounts.manage sees everyone's.",
    responses=errors(401, 422),
)
async def list_enrollments(
    query: Annotated[EnrollmentListQuery, Query()], auth: CurrentAuth, db: DbSession, settings: SettingsDep
) -> EnrollmentListResponse:
    organization_ids: tuple[int, ...] | None
    if sees_all_institutions(auth):
        organization_ids, student_user_id = institutions_in_care(auth), None
    elif sees_own_batches(auth):
        organization_ids, student_user_id = (auth.organization_id or 0,), None
    elif auth.has_scope(STUDY):
        organization_ids, student_user_id = None, auth.user_id
    else:
        raise PermissionDeniedError()

    enrollments, total, is_exact = await EnrollmentService(db, settings).list_enrollments(
        query,
        batch_id=parse_public_id(query.batch_id) if query.batch_id else None,
        organization_ids=organization_ids,
        student_user_id=student_user_id,
    )
    return EnrollmentListResponse(
        message="Enrollments retrieved successfully.",
        enrollments=[EnrollmentOut.model_validate(enrollment) for enrollment in enrollments],
        page_context=PageContext.build(
            page=query.page, per_page=query.per_page, total=total, is_exact=is_exact,
            sort_column="created_time", sort_order=SortOrder(query.sort_order),
        ),
    )


@router.get("/enrollments/{enrollment_id}", response_model=EnrollmentResponse, summary="Get an enrolment", responses=errors(401, 403, 404))
async def get_enrollment(enrollment_id: EnrollmentIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> EnrollmentResponse:
    enrollment = await EnrollmentService(db, settings).get(enrollment_id)
    _ensure_enrollment_visible(auth, enrollment)
    return EnrollmentResponse(message="Enrolment retrieved successfully.", enrollment=EnrollmentOut.model_validate(enrollment))


@router.post(
    "/enrollments/{enrollment_id}/withdraw",
    response_model=EnrollmentResponse,
    summary="Withdraw a student from a batch",
    description="Releases the reserved seat on the batch's subscription.",
    responses=errors(400, 401, 403, 404, 422),
)
async def withdraw_enrollment(enrollment_id: EnrollmentIdParam, auth: RequireBatchRevoke, db: DbSession, settings: SettingsDep) -> EnrollmentResponse:
    service = EnrollmentService(db, settings)
    enrollment = await service.get(enrollment_id)
    ensure_organization_visible(auth, enrollment.batch.organization_id)
    enrollment = await service.withdraw(enrollment, enrollment.batch)
    return EnrollmentResponse(message="Student withdrawn.", enrollment=EnrollmentOut.model_validate(enrollment))
