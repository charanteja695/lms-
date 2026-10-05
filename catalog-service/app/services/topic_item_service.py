import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.ids import new_public_id
from app.db.session import commit_or_conflict
from app.models.topic import Topic
from app.models.topic_item import TopicItem
from app.schemas.topic_item import TopicItemCreate, TopicItemUpdate


class TopicItemService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, topic: Topic, data: TopicItemCreate) -> TopicItem:
        next_position = await self._next_position(topic.id)
        item = TopicItem(
            public_id=new_public_id(),
            topic_id=topic.id,
            item_type=data.item_type,
            title=data.title,
            position=next_position,
            required=data.required,
            media_id=data.media_id,
            content_text=data.content_text,
        )
        self.db.add(item)
        await commit_or_conflict(self.db)
        return item

    async def get(self, topic: Topic, topic_item_id: int) -> TopicItem:
        item = (
            await self.db.execute(
                select(TopicItem).where(TopicItem.topic_id == topic.id, TopicItem.public_id == topic_item_id)
            )
        ).scalar_one_or_none()
        if item is None:
            raise NotFoundError("Topic item not found.", code="TOPIC_ITEM_NOT_FOUND")
        return item

    async def update(self, item: TopicItem, data: TopicItemUpdate) -> TopicItem:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        await commit_or_conflict(self.db)
        return item

    async def delete(self, item: TopicItem) -> None:
        await self.db.delete(item)
        await self.db.commit()

    async def reorder(self, topic: Topic, ordered_item_ids: list[int]) -> None:
        items = list(
            (
                await self.db.execute(
                    select(TopicItem).where(TopicItem.topic_id == topic.id, TopicItem.public_id.in_(ordered_item_ids))
                )
            )
            .scalars()
            .all()
        )
        by_public_id = {item.public_id: item for item in items}
        if set(by_public_id) != set(ordered_item_ids):
            raise NotFoundError("One or more items were not found in this topic.", code="TOPIC_ITEM_NOT_FOUND")
        for position, item_id in enumerate(ordered_item_ids, start=1):
            by_public_id[item_id].position = position
        await self.db.commit()

    async def _next_position(self, topic_id: uuid.UUID) -> int:
        current_max = (
            await self.db.execute(select(func.max(TopicItem.position)).where(TopicItem.topic_id == topic_id))
        ).scalar_one()
        return (current_max or 0) + 1
