from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder
from sqlalchemy import select
from sqlalchemy.orm import selectinload

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
from app.clients.entitlement_cache import get_entitlement
from app.clients.subscription_client import get_active_subscription
from app.core.exceptions import AuthenticationError, BadRequestError, NotFoundError, PermissionDeniedError
from app.core.ids import new_public_id, parse_public_id
from app.core.security import AccessTokenClaims
from app.domain.enums import BatchStatus, EnrollmentStatus
from app.models.batch import Batch
from app.models.enrollment import Enrollment
from app.schemas.enrollment import (
    EnrollmentCreate,
    EnrollmentListQuery,
    EnrollmentListResponse,
    EnrollmentOut,
    EnrollmentResponse,
)
from app.services.batch_service import BatchService
from app.services.course_structure_service import CourseStructureService
from app.services.enrollment_service import EnrollmentService
from app.services.institution_ref_service import InstitutionRefService

router = APIRouter(tags=["Enrollments"])


def _ensure_enrollment_visible(auth: AccessTokenClaims, enrollment: Enrollment) -> None:
    if auth.user_id == enrollment.student_user_id:
        return
    ensure_organization_visible(auth, enrollment.batch.organization_id)


@router.post(
    "/enrollments/courses/{course_id}/self-enroll",
    response_model=EnrollmentResponse,
    status_code=201,
    summary="Self-enroll an institution student into a course",
    description="Validates institution subscription, term dates, seat availability, provisions batch if needed, reserves seat and enrolls student.",
    responses=errors(400, 401, 403, 404, 409, 422),
)
async def self_enroll_course(
    course_id: str,
    auth: CurrentAuth,
    db: DbSession,
    settings: SettingsDep,
    redis: RedisDep,
) -> EnrollmentResponse:
    parsed_course_id = parse_public_id(course_id)
    if parsed_course_id is None:
        raise NotFoundError("Course not found.", code="COURSE_NOT_FOUND")

    # 1. Validate student authentication
    if not auth.user_id:
        raise AuthenticationError("Log in to continue.", code="NOT_AUTHENTICATED")

    # 2. Validate institution association
    if not auth.organization_id:
        raise BadRequestError(
            "Self-enrollment via institutional package is only available for institution students. Please purchase the course or contact your administrator.",
            code="NOT_INSTITUTION_STUDENT",
        )

    # 3. Validate institution is active in local read-model
    await InstitutionRefService(db).get_active(auth.organization_id)

    # 4. Get latest published course version
    version = await CourseStructureService(db).get_latest_published_for_course(parsed_course_id)

    # 5. Check if student is already enrolled in this course version
    existing_stmt = (
        select(Enrollment)
        .join(Batch, Enrollment.batch_id == Batch.id)
        .where(
            Enrollment.student_user_id == auth.user_id,
            Batch.version_id == version.version_id,
            Enrollment.status == EnrollmentStatus.ACTIVE,
        )
        .options(selectinload(Enrollment.batch))
    )
    existing_enrollment = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing_enrollment is not None:
        return EnrollmentResponse(
            message="Already enrolled in this course.",
            enrollment=EnrollmentOut.model_validate(existing_enrollment),
        )

    # 6. Verify institutional entitlement / subscription
    entitlement = await get_entitlement(
        redis,
        key_prefix=settings.ENTITLEMENT_KEY_PREFIX,
        organization_id=auth.organization_id,
        course_id=parsed_course_id,
    )

    subscription_id: int | None = entitlement.subscription_id if entitlement else None

    # If not cached in Redis, check subscription-service directly
    if subscription_id is None:
        sub_info = await get_active_subscription(settings, auth.organization_id, parsed_course_id)
        if sub_info:
            subscription_id = int(sub_info["subscription_id"])
            if int(sub_info.get("seats_used", 0)) >= int(sub_info.get("seats_total", 0)):
                raise BadRequestError(
                    "All institutional seats for this course have been allocated. Please contact your administrator.",
                    code="NO_SEATS_AVAILABLE",
                )

    if subscription_id is None:
        raise BadRequestError(
            "Your institution does not have an active package for this course.",
            code="NO_ACTIVE_SUBSCRIPTION",
        )

    # 7. Find or provision active institutional batch
    batch_stmt = (
        select(Batch)
        .where(
            Batch.organization_id == auth.organization_id,
            Batch.version_id == version.version_id,
            Batch.status == BatchStatus.ACTIVE,
        )
        .options(selectinload(Batch.course_version))
    )
    batch = (await db.execute(batch_stmt)).scalar_one_or_none()

    if batch is None:
        batch = Batch(
            public_id=new_public_id(),
            organization_id=auth.organization_id,
            version_id=version.version_id,
            subscription_id=subscription_id,
            name=f"{version.title} · Institution Batch",
            status=BatchStatus.ACTIVE,
            created_by=auth.user_id,
        )
        db.add(batch)
        await db.flush()
        batch.course_version = version

    # 8. Enroll student and reserve seat atomically in subscription-service
    enrollment = await EnrollmentService(db, settings).enroll(batch, auth.user_id)

    return EnrollmentResponse(
        message="Enrolled successfully! Ready to start learning.",
        enrollment=EnrollmentOut.model_validate(enrollment),
    )


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
