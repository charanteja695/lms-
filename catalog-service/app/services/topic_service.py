import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.ids import new_public_id
from app.db.session import commit_or_conflict
from app.models.module import Module
from app.models.topic import Topic
from app.schemas.topic import TopicCreate, TopicUpdate


class TopicService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, module: Module, data: TopicCreate) -> Topic:
        next_position = await self._next_position(module.id)
        topic = Topic(
            public_id=new_public_id(),
            module_id=module.id,
            title=data.title,
            position=next_position,
            pass_mark=data.pass_mark,
        )
        self.db.add(topic)
        await commit_or_conflict(self.db)
        return topic

    async def get(self, module: Module, topic_id: int) -> Topic:
        topic = (
            await self.db.execute(select(Topic).where(Topic.module_id == module.id, Topic.public_id == topic_id))
        ).scalar_one_or_none()
        if topic is None:
            raise NotFoundError("Topic not found.", code="TOPIC_NOT_FOUND")
        return topic

    async def update(self, topic: Topic, data: TopicUpdate) -> Topic:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(topic, field, value)
        await commit_or_conflict(self.db)
        return topic

    async def delete(self, topic: Topic) -> None:
        await self.db.delete(topic)
        await self.db.commit()

    async def reorder(self, module: Module, ordered_topic_ids: list[int]) -> None:
        topics = list(
            (await self.db.execute(select(Topic).where(Topic.module_id == module.id, Topic.public_id.in_(ordered_topic_ids))))
            .scalars()
            .all()
        )
        by_public_id = {topic.public_id: topic for topic in topics}
        if set(by_public_id) != set(ordered_topic_ids):
            raise NotFoundError("One or more topics were not found in this module.", code="TOPIC_NOT_FOUND")
        for position, topic_id in enumerate(ordered_topic_ids, start=1):
            by_public_id[topic_id].position = position
        await self.db.commit()

    async def _next_position(self, module_id: uuid.UUID) -> int:
        current_max = (await self.db.execute(select(func.max(Topic.position)).where(Topic.module_id == module_id))).scalar_one()
        return (current_max or 0) + 1
