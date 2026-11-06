from fastapi import APIRouter

from app.api.deps import DbSession, RequireAuthor
from app.api.responses import errors
from app.api.v1.authoring_deps import ModuleInVersion, TopicInModule
from app.schemas.common import ReorderRequest
from app.schemas.topic import TopicCreate, TopicOut, TopicResponse, TopicUpdate
from app.services.topic_service import TopicService

router = APIRouter(prefix="/courses/{course_id}/versions/{version_id}/modules/{module_id}/topics", tags=["Topics"])


@router.post("", response_model=TopicResponse, status_code=201, summary="Add a topic", responses=errors(400, 401, 403, 404, 422))
async def create_topic(module: ModuleInVersion, data: TopicCreate, auth: RequireAuthor, db: DbSession) -> TopicResponse:
    topic = await TopicService(db).create(module, data)
    return TopicResponse(message="Topic added successfully.", topic=TopicOut.model_validate(topic))


@router.patch("/{topic_id}", response_model=TopicResponse, summary="Update a topic", responses=errors(400, 401, 403, 404, 422))
async def update_topic(topic: TopicInModule, data: TopicUpdate, auth: RequireAuthor, db: DbSession) -> TopicResponse:
    topic = await TopicService(db).update(topic, data)
    return TopicResponse(message="Topic updated successfully.", topic=TopicOut.model_validate(topic))


@router.delete("/{topic_id}", status_code=204, summary="Remove a topic", responses=errors(400, 401, 403, 404))
async def delete_topic(topic: TopicInModule, auth: RequireAuthor, db: DbSession) -> None:
    await TopicService(db).delete(topic)


@router.put("/reorder", status_code=204, summary="Reorder topics", responses=errors(400, 401, 403, 404, 422))
async def reorder_topics(module: ModuleInVersion, data: ReorderRequest, auth: RequireAuthor, db: DbSession) -> None:
    await TopicService(db).reorder(module, data.ordered_ids)
