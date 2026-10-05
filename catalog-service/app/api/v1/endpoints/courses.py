from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import CourseIdParam, DbSession, RequireAuthor
from app.api.responses import errors
from app.schemas.course import (
    CourseCreate,
    CourseListQuery,
    CourseListResponse,
    CourseOut,
    CourseResponse,
    CourseUpdate,
)
from app.services.course_service import CourseService

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
async def list_courses(query: Annotated[CourseListQuery, Query()], db: DbSession) -> CourseListResponse:
    courses, total, is_exact = await CourseService(db).list_courses(query)
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
    "/{course_id}",
    response_model=CourseResponse,
    summary="Get a course",
    responses=errors(401, 404),
)
async def get_course(course_id: CourseIdParam, db: DbSession) -> CourseResponse:
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
