from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import CourseIdParam, DbSession, LearningPathIdParam, RequireAuthor
from app.api.responses import errors
from app.schemas.common import ListQuery, ReorderRequest
from app.schemas.learning_path import (
    LearningPathCreate,
    LearningPathItemAdd,
    LearningPathListResponse,
    LearningPathOut,
    LearningPathResponse,
    LearningPathUpdate,
)
from app.services.learning_path_service import LearningPathService

router = APIRouter(prefix="/learning-paths", tags=["Learning paths"])


@router.post("", response_model=LearningPathResponse, status_code=201, summary="Create a learning path", responses=errors(401, 403, 409, 422))
async def create_learning_path(data: LearningPathCreate, auth: RequireAuthor, db: DbSession) -> LearningPathResponse:
    path = await LearningPathService(db).create(auth.user_id, data)
    return LearningPathResponse(message="Learning path created successfully.", learning_path=LearningPathOut.model_validate(path))


@router.get("", response_model=LearningPathListResponse, summary="List learning paths", responses=errors(401, 422))
async def list_learning_paths(query: Annotated[ListQuery, Query()], db: DbSession) -> LearningPathListResponse:
    paths, total, is_exact = await LearningPathService(db).list_learning_paths(query)
    return LearningPathListResponse(
        message="Learning paths retrieved successfully.",
        learning_paths=[LearningPathOut.model_validate(path) for path in paths],
        page_context=PageContext.build(
            page=query.page, per_page=query.per_page, total=total, is_exact=is_exact,
            sort_column="created_time", sort_order=SortOrder(query.sort_order),
        ),
    )


@router.get("/{learning_path_id}", response_model=LearningPathResponse, summary="Get a learning path", responses=errors(401, 404))
async def get_learning_path(learning_path_id: LearningPathIdParam, db: DbSession) -> LearningPathResponse:
    path = await LearningPathService(db).get(learning_path_id)
    return LearningPathResponse(message="Learning path retrieved successfully.", learning_path=LearningPathOut.model_validate(path))


@router.patch("/{learning_path_id}", response_model=LearningPathResponse, summary="Update a draft learning path", responses=errors(401, 403, 404, 409, 422))
async def update_learning_path(learning_path_id: LearningPathIdParam, data: LearningPathUpdate, auth: RequireAuthor, db: DbSession) -> LearningPathResponse:
    service = LearningPathService(db)
    path = await service.get(learning_path_id)
    path = await service.update(path, data)
    return LearningPathResponse(message="Learning path updated successfully.", learning_path=LearningPathOut.model_validate(path))


@router.post("/{learning_path_id}/courses", response_model=LearningPathResponse, summary="Add a course to a draft learning path", responses=errors(401, 403, 404, 409, 422))
async def add_course(learning_path_id: LearningPathIdParam, data: LearningPathItemAdd, auth: RequireAuthor, db: DbSession) -> LearningPathResponse:
    service = LearningPathService(db)
    path = await service.get(learning_path_id)
    path = await service.add_course(path, data.course_id)
    return LearningPathResponse(message="Course added to the learning path.", learning_path=LearningPathOut.model_validate(path))


@router.delete("/{learning_path_id}/courses/{course_id}", response_model=LearningPathResponse, summary="Remove a course from a draft learning path", responses=errors(400, 401, 403, 404))
async def remove_course(learning_path_id: LearningPathIdParam, course_id: CourseIdParam, auth: RequireAuthor, db: DbSession) -> LearningPathResponse:
    service = LearningPathService(db)
    path = await service.get(learning_path_id)
    path = await service.remove_course(path, course_id)
    return LearningPathResponse(message="Course removed from the learning path.", learning_path=LearningPathOut.model_validate(path))


@router.put("/{learning_path_id}/courses/reorder", response_model=LearningPathResponse, summary="Reorder courses in a draft learning path", responses=errors(400, 401, 403, 404, 422))
async def reorder_courses(learning_path_id: LearningPathIdParam, data: ReorderRequest, auth: RequireAuthor, db: DbSession) -> LearningPathResponse:
    service = LearningPathService(db)
    path = await service.get(learning_path_id)
    path = await service.reorder(path, data.ordered_ids)
    return LearningPathResponse(message="Learning path reordered successfully.", learning_path=LearningPathOut.model_validate(path))


@router.post("/{learning_path_id}/publish", response_model=LearningPathResponse, summary="Publish a learning path", responses=errors(400, 401, 403, 404))
async def publish_learning_path(learning_path_id: LearningPathIdParam, auth: RequireAuthor, db: DbSession) -> LearningPathResponse:
    service = LearningPathService(db)
    path = await service.get(learning_path_id)
    path = await service.publish(path)
    return LearningPathResponse(message="Learning path published.", learning_path=LearningPathOut.model_validate(path))


@router.post("/{learning_path_id}/archive", response_model=LearningPathResponse, summary="Archive a published learning path", responses=errors(400, 401, 403, 404))
async def archive_learning_path(learning_path_id: LearningPathIdParam, auth: RequireAuthor, db: DbSession) -> LearningPathResponse:
    service = LearningPathService(db)
    path = await service.get(learning_path_id)
    path = await service.archive(path)
    return LearningPathResponse(message="Learning path archived.", learning_path=LearningPathOut.model_validate(path))
