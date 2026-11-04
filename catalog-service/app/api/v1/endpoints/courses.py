from app.services.review_service import ReviewService
from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder, SuccessResponse

from app.api.deps import CourseIdParam, CurrentAuth, DbSession, RequireAuthor
from app.api.responses import errors
from app.core.exceptions import PermissionDeniedError
from app.core.time import utcnow
from app.domain.enums import ContentStatus, ReviewAction
from app.models.review import CourseReview
from app.schemas.course import (
    CourseCreate,
    CourseListQuery,
    CourseListResponse,
    CourseOut,
    CourseResponse,
    CourseUpdate,
    BulkDeleteRequest,
    BulkDeleteResponse,
    CatalogCleanupSummaryResponse,
)
from app.services.course_service import CourseService
from app.services.outbox import write_event

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.post(
    "",
    response_model=CourseResponse,
    status_code=201,
    summary="Create a course",
    description="Creates the course shell and its first draft version (v1). Requires content.author.",
    responses=errors(401, 403, 409, 422),
)
async def create_course(data: CourseCreate, auth: RequireAuthor, db: DbSession) -> CourseResponse:
    course = await CourseService(db).create(auth.user_id, data)
    return CourseResponse(message="Course created successfully.", course=CourseOut.model_validate(course))


@router.get(
    "",
    response_model=CourseListResponse,
    summary="List courses",
    responses=errors(401, 422),
)
async def list_courses(query: Annotated[CourseListQuery, Query()], auth: CurrentAuth, db: DbSession) -> CourseListResponse:
    is_admin = auth.role in ("super_admin", "admin") or auth.can("content.author")
    published_only = query.published_only or not is_admin
    courses, total, is_exact = await CourseService(db).list_courses(query, published_only=published_only)
    return CourseListResponse(
        message="Courses retrieved successfully.",
        courses=[CourseOut.model_validate(course) for course in courses],
        page_context=PageContext.build(
            page=query.page,
            per_page=query.per_page,
            total=total,
            is_exact=is_exact,
            sort_column="created_time",
            sort_order=SortOrder(query.sort_order),
        ),
    )


@router.get(
    "/cleanup-summary",
    response_model=CatalogCleanupSummaryResponse,
    summary="Get catalog cleanup statistics",
    description="Returns metrics on active, published, and draft courses, modules, and chapters. Requires admin or content.author.",
    responses=errors(401, 403),
)
async def get_cleanup_summary(auth: CurrentAuth, db: DbSession) -> CatalogCleanupSummaryResponse:
    if not (auth.role in ("super_admin", "admin") or auth.can("content.author")):
        raise PermissionDeniedError()
    summary = await CourseService(db).get_cleanup_summary()
    return CatalogCleanupSummaryResponse(
        message="Catalog cleanup summary retrieved successfully.",
        **summary
    )


@router.post(
    "/bulk-delete",
    response_model=BulkDeleteResponse,
    summary="Bulk delete or clear active courses",
    description="Deletes selected courses or clears all active courses. Requires admin or content.author for selected; super_admin for clear_all_active.",
    responses=errors(401, 403, 422),
)
async def bulk_delete_courses(data: BulkDeleteRequest, auth: CurrentAuth, db: DbSession) -> BulkDeleteResponse:
    if data.clear_all_active:
        if auth.role != "super_admin":
            raise PermissionDeniedError("Only Super Admins can clear the entire active course catalog.")
    else:
        if not (auth.role in ("super_admin", "admin") or auth.can("content.author")):
            raise PermissionDeniedError()

    from app.core.ids import parse_public_id
    parsed_ids = []
    for cid in data.course_ids:
        pid = parse_public_id(cid)
        if pid is not None:
            parsed_ids.append(pid)

    count, titles = await CourseService(db).bulk_delete(
        course_ids=parsed_ids if not data.clear_all_active else None,
        clear_all_active=data.clear_all_active,
    )
    return BulkDeleteResponse(
        message=f"Successfully deleted {count} course{'s' if count != 1 else ''}.",
        deleted_count=count,
        affected_courses=titles,
    )


@router.get(
    "/{course_id}",
    response_model=CourseResponse,
    summary="Get a course",
    responses=errors(401, 404),
)
async def get_course(course_id: CourseIdParam, auth: CurrentAuth, db: DbSession) -> CourseResponse:
    course = await CourseService(db).get(course_id)
    return CourseResponse(message="Course retrieved successfully.", course=CourseOut.model_validate(course))


@router.patch(
    "/{course_id}",
    response_model=CourseResponse,
    summary="Update a course",
    description="Updates course-level metadata (title, summary, thumbnail). Requires content.author.",
    responses=errors(401, 403, 404, 409, 422),
)
async def update_course(course_id: CourseIdParam, data: CourseUpdate, auth: RequireAuthor, db: DbSession) -> CourseResponse:
    service = CourseService(db)
    course = await service.get(course_id)
    course = await service.update(course, data)
    return CourseResponse(message="Course updated successfully.", course=CourseOut.model_validate(course))


@router.delete(
    "/{course_id}",
    response_model=SuccessResponse,
    summary="Delete / archive a course",
    description="Archives a course so it no longer appears in the active catalogue. Requires content.author.",
    responses=errors(401, 403, 404),
)
async def delete_course(course_id: CourseIdParam, auth: RequireAuthor, db: DbSession) -> SuccessResponse:
    service = CourseService(db)
    course = await service.get(course_id)
    await service.delete(course)
    return SuccessResponse(message="Course archived successfully.")


@router.post(
    "/{course_id}/publish",
    response_model=CourseResponse,
    summary="Publish a course",
    description="Publishes the course so institutions can request access. Requires admin or content.author.",
    responses=errors(401, 403, 404),
)
async def publish_course(course_id: CourseIdParam, auth: CurrentAuth, db: DbSession) -> CourseResponse:
    if not (auth.role in ("super_admin", "admin") or auth.can("content.author")):
        raise PermissionDeniedError()
    service = CourseService(db)
    course = await service.get(course_id)

    target_version = None
    for v in course.versions:
        if v.status in (ContentStatus.DRAFT, ContentStatus.IN_REVIEW):
            target_version = v
            break
    if target_version is None and course.versions:
        target_version = sorted(course.versions, key=lambda x: x.version_number, reverse=True)[0]

    if target_version is not None:
        target_version.status = ContentStatus.PUBLISHED
        target_version.published_at = utcnow()
        target_version.reviewed_by = auth.user_id
        target_version.reviewed_at = utcnow()
        db.add(CourseReview(course_version_id=target_version.id, action=ReviewAction.APPROVED, actor_user_id=auth.user_id))
        write_event(
            db,
            event_type="course.published",
            aggregate_id=course.id,
            payload={
                "course_id": str(course.public_id),
                "version_id": str(target_version.public_id),
                "title": course.title,
                "slug": course.slug,
            },
        )
        await db.commit()
        await ReviewService(db).sync_published_curriculum(target_version)

        try:
            import asyncpg
            conn = await asyncpg.connect("postgresql://lms:lms@localhost:5432/lms_subscription")
            try:
                await conn.execute("""
                    INSERT INTO course_refs (course_id, title, slug, status, created_at, updated_at)
                    VALUES ($1, $2, $3, 'published', NOW(), NOW())
                    ON CONFLICT (course_id) DO UPDATE SET title = EXCLUDED.title, slug = EXCLUDED.slug, status = 'published', updated_at = NOW()
                """, course.public_id, course.title, course.slug)
            finally:
                await conn.close()
        except Exception:
            pass

    return CourseResponse(message="Course published successfully.", course=CourseOut.model_validate(await service.get(course_id)))


@router.post(
    "/{course_id}/unpublish",
    response_model=CourseResponse,
    summary="Unpublish a course to draft",
    description="Reverts a published course to draft. Requires admin or content.author.",
    responses=errors(401, 403, 404),
)
async def unpublish_course(course_id: CourseIdParam, auth: CurrentAuth, db: DbSession) -> CourseResponse:
    if not (auth.role in ("super_admin", "admin") or auth.can("content.author")):
        raise PermissionDeniedError()
    service = CourseService(db)
    course = await service.get(course_id)

    for v in course.versions:
        if v.status == ContentStatus.PUBLISHED:
            v.status = ContentStatus.DRAFT

    await db.commit()

    try:
        import asyncpg
        conn = await asyncpg.connect("postgresql://lms:lms@localhost:5432/lms_subscription")
        try:
            await conn.execute("""
                UPDATE course_refs SET status = 'retired', updated_at = NOW() WHERE course_id = $1
            """, course.public_id)
        finally:
            await conn.close()
    except Exception:
        pass

    return CourseResponse(message="Course reverted to draft.", course=CourseOut.model_validate(await service.get(course_id)))
