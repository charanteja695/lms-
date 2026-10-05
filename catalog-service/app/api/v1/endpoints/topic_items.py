from fastapi import APIRouter

from app.api.deps import DbSession, RequireAuthor
from app.api.responses import errors
from app.api.v1.authoring_deps import ItemInTopic, TopicInModule
from app.schemas.common import ReorderRequest
from app.schemas.topic_item import TopicItemCreate, TopicItemOut, TopicItemResponse, TopicItemUpdate
from app.services.topic_item_service import TopicItemService

router = APIRouter(
    prefix="/courses/{course_id}/versions/{version_id}/modules/{module_id}/topics/{topic_id}/items",
    tags=["Topic items"],
)


@router.post("", response_model=TopicItemResponse, status_code=201, summary="Add a topic item", responses=errors(400, 401, 403, 404, 422))
async def create_item(topic: TopicInModule, data: TopicItemCreate, auth: RequireAuthor, db: DbSession) -> TopicItemResponse:
    item = await TopicItemService(db).create(topic, data)
    return TopicItemResponse(message="Item added successfully.", topic_item=TopicItemOut.model_validate(item))


@router.patch("/{topic_item_id}", response_model=TopicItemResponse, summary="Update a topic item", responses=errors(400, 401, 403, 404, 422))
async def update_item(item: ItemInTopic, data: TopicItemUpdate, auth: RequireAuthor, db: DbSession) -> TopicItemResponse:
    item = await TopicItemService(db).update(item, data)
    return TopicItemResponse(message="Item updated successfully.", topic_item=TopicItemOut.model_validate(item))


@router.delete("/{topic_item_id}", status_code=204, summary="Remove a topic item", responses=errors(400, 401, 403, 404))
async def delete_item(item: ItemInTopic, auth: RequireAuthor, db: DbSession) -> None:
    await TopicItemService(db).delete(item)


@router.put("/reorder", status_code=204, summary="Reorder topic items", responses=errors(400, 401, 403, 404, 422))
async def reorder_items(topic: TopicInModule, data: ReorderRequest, auth: RequireAuthor, db: DbSession) -> None:
    await TopicItemService(db).reorder(topic, data.ordered_ids)
