from app.services.institution_access import check_student_course_access
from fastapi import APIRouter
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import (
    CourseIdParam,
    DbSession,
    RequireAuthor,
    RequireDraftReader,
    RequireReader,
    RequireReviewer,
    VersionIdParam,
    sees_drafts,
)
from app.api.responses import errors
from app.core.exceptions import NotFoundError
from app.domain.enums import ContentStatus
from app.schemas.course_rule import CourseRuleOut, CourseRuleUpdate
from app.schemas.review import RejectRequest, ReviewListResponse, ReviewOut
from app.schemas.version import (
    CourseVersionDetail,
    CourseVersionDetailResponse,
    CourseVersionOut,
    CourseVersionResponse,
)
from app.services.course_service import CourseService
from app.services.review_service import ReviewService
from app.services.version_service import VersionService

router = APIRouter(prefix="/courses/{course_id}/versions", tags=["Course versions"])


@router.post(
    "",
    response_model=CourseVersionResponse,
    status_code=201,
    summary="Start a new draft version",
    description="Only one draft/in-review version may exist per course at a time. Requires content.author.",
    responses=errors(401, 403, 404, 409, 422),
)
async def create_draft(course_id: CourseIdParam, auth: RequireAuthor, db: DbSession) -> CourseVersionResponse:
    course = await CourseService(db).get(course_id)
    version = await VersionService(db).create_draft(course, auth.user_id)
    return CourseVersionResponse(
        message="Draft version created successfully.", version=CourseVersionOut.model_validate(version)
    )


@router.get(
    "/{version_id}",
    response_model=CourseVersionDetailResponse,
    summary="Get a course version",
    description="Full authoring tree: rules, modules, topics and topic items.",
    responses=errors(401, 404),
)
async def get_version(course_id: CourseIdParam, version_id: VersionIdParam, auth: RequireReader, db: DbSession) -> CourseVersionDetailResponse:
    if auth.role == "student":
        has_access = await check_student_course_access(auth.organization_id, course_id)
        if not has_access:
            raise PermissionDeniedError(
                "Your institution has not been granted access to this course.",
                code="COURSE_ACCESS_DENIED"
            )
    version = await VersionService(db).get_detail(course_id, version_id)
    if version.status not in (ContentStatus.PUBLISHED, ContentStatus.ARCHIVED) and not sees_drafts(auth):
        raise NotFoundError("Course version not found.", code="COURSE_VERSION_NOT_FOUND")  # a draft is its authors' business
    return CourseVersionDetailResponse(
        message="Course version retrieved successfully.", version=CourseVersionDetail.model_validate(version)
    )


@router.patch(
    "/{version_id}/rules",
    response_model=CourseRuleOut,
    summary="Update a draft version's rules",
    responses=errors(401, 403, 404, 422),
)
async def update_rules(
    course_id: CourseIdParam, version_id: VersionIdParam, data: CourseRuleUpdate, auth: RequireAuthor, db: DbSession
) -> CourseRuleOut:
    service = VersionService(db)
    version = await service.get_detail(course_id, version_id)
    service.ensure_draft(version)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(version.rule, field, value)
    await db.commit()
    if version.status == ContentStatus.PUBLISHED:
        await ReviewService(db).sync_published_curriculum(version)
    return CourseRuleOut.model_validate(version.rule)


@router.post(
    "/{version_id}/submit",
    response_model=CourseVersionResponse,
    summary="Submit a draft for review",
    responses=errors(400, 401, 403, 404),
)
async def submit(course_id: CourseIdParam, version_id: VersionIdParam, auth: RequireAuthor, db: DbSession) -> CourseVersionResponse:
    version = await VersionService(db).get(course_id, version_id)
    version = await ReviewService(db).submit(version, auth.user_id)
    return CourseVersionResponse(message="Submitted for review.", version=CourseVersionOut.model_validate(version))


@router.post(
    "/{version_id}/approve",
    response_model=CourseVersionResponse,
    summary="Approve and publish a version",
    responses=errors(400, 401, 403, 404),
)
async def approve(course_id: CourseIdParam, version_id: VersionIdParam, auth: RequireReviewer, db: DbSession) -> CourseVersionResponse:
    version = await VersionService(db).get(course_id, version_id)
    version = await ReviewService(db).approve(version, auth.user_id)
    return CourseVersionResponse(message="Course version published.", version=CourseVersionOut.model_validate(version))


@router.post(
    "/{version_id}/reject",
    response_model=CourseVersionResponse,
    summary="Reject a version back to draft",
    responses=errors(400, 401, 403, 404, 422),
)
async def reject(
    course_id: CourseIdParam, version_id: VersionIdParam, data: RejectRequest, auth: RequireReviewer, db: DbSession
) -> CourseVersionResponse:
    version = await VersionService(db).get(course_id, version_id)
    version = await ReviewService(db).reject(version, auth.user_id, data.reason)
    return CourseVersionResponse(message="Sent back to draft.", version=CourseVersionOut.model_validate(version))


@router.post(
    "/{version_id}/retire",
    response_model=CourseVersionResponse,
    summary="Retire a published version",
    responses=errors(400, 401, 403, 404),
)
async def retire(course_id: CourseIdParam, version_id: VersionIdParam, auth: RequireReviewer, db: DbSession) -> CourseVersionResponse:
    version = await VersionService(db).get(course_id, version_id)
    version = await ReviewService(db).retire(version, auth.user_id)
    return CourseVersionResponse(message="Course version retired.", version=CourseVersionOut.model_validate(version))


@router.get(
    "/{version_id}/reviews",
    response_model=ReviewListResponse,
    summary="Lifecycle audit trail for a version",
    responses=errors(401, 404),
)
async def list_reviews(course_id: CourseIdParam, version_id: VersionIdParam, auth: RequireDraftReader, db: DbSession) -> ReviewListResponse:
    version = await VersionService(db).get(course_id, version_id)
    reviews = await ReviewService(db).list_reviews(version)
    return ReviewListResponse(
        message="Reviews retrieved successfully.",
        reviews=[ReviewOut.model_validate(review) for review in reviews],
        page_context=PageContext.build(
            page=1, per_page=len(reviews) or 1, total=len(reviews), is_exact=True,
            sort_column="created_time", sort_order=SortOrder.DESC,
        ),
    )
