import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.domain.enums import ContentStatus
from app.models.course_version import CourseVersion
from app.models.module import Module
from app.services.review_service import ReviewService
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
            media_ready=bool(data.media_id),
            content_text=data.content_text,
        )
        self.db.add(item)
        await commit_or_conflict(self.db)
        module = (await self.db.execute(select(Module).where(Module.id == topic.module_id))).scalar_one_or_none()
        if module:
            version = (await self.db.execute(select(CourseVersion).where(CourseVersion.id == module.course_version_id))).scalar_one_or_none()
            if version and version.status == ContentStatus.PUBLISHED:
                await ReviewService(self.db).sync_published_curriculum(version)
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
        topic = (await self.db.execute(select(Topic).where(Topic.id == item.topic_id))).scalar_one_or_none()
        if topic:
            module = (await self.db.execute(select(Module).where(Module.id == topic.module_id))).scalar_one_or_none()
            if module:
                version = (await self.db.execute(select(CourseVersion).where(CourseVersion.id == module.course_version_id))).scalar_one_or_none()
                if version and version.status == ContentStatus.PUBLISHED:
                    await ReviewService(self.db).sync_published_curriculum(version)
        return item

    async def delete(self, item: TopicItem) -> None:
        try:
            import asyncpg
            conn = await asyncpg.connect("postgresql://lms:lms@127.0.0.1:5432/lms_learning")
            try:
                prog_count = await conn.fetchval('''
                    SELECT COUNT(*) FROM item_progress WHERE topic_item_id = $1
                ''', item.public_id)
                if (prog_count or 0) > 0:
                    raise BadRequestError(
                        "Cannot delete learning material because student progress exists for it.",
                        code="STUDENT_PROGRESS_EXISTS"
                    )
                await conn.execute("DELETE FROM topic_item_refs WHERE topic_item_id = $1", item.public_id)
            finally:
                await conn.close()
        except BadRequestError:
            raise
        except Exception:
            pass

        topic = (await self.db.execute(select(Topic).where(Topic.id == item.topic_id))).scalar_one_or_none()
        await self.db.delete(item)
        await self.db.commit()
        if topic:
            module = (await self.db.execute(select(Module).where(Module.id == topic.module_id))).scalar_one_or_none()
            if module:
                version = (await self.db.execute(select(CourseVersion).where(CourseVersion.id == module.course_version_id))).scalar_one_or_none()
                if version and version.status == ContentStatus.PUBLISHED:
                    await ReviewService(self.db).sync_published_curriculum(version)

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
