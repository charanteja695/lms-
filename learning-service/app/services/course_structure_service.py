from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.domain.enums import CourseVersionStatus
from app.models.course_version_ref import CourseVersionRef
from app.models.module_ref import ModuleRef
from app.models.topic_item_ref import TopicItemRef
from app.models.topic_ref import TopicRef

_LOAD_TREE = selectinload(CourseVersionRef.modules).selectinload(ModuleRef.topics).selectinload(TopicRef.items)


class CourseStructureService:
    """Builds/updates the local mirror of a published course version from catalog-service's
    ``course.published`` event, which carries the full authoring tree for exactly this reason
    (see catalog-service's ``ReviewService._published_structure_payload``)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert_published(self, payload: dict[str, Any]) -> None:
        version_id = int(payload["version_id"])
        version = await self.db.get(CourseVersionRef, version_id)
        if version is None:
            version = CourseVersionRef(
                version_id=version_id,
                course_id=int(payload["course_id"]),
                title=payload["title"],
                slug=payload["slug"],
                final_pass_mark=payload["final_pass_mark"],
                final_test_attempts=payload["final_test_attempts"],
                final_test_cooldown_days=payload["final_test_cooldown_days"],
            )
            self.db.add(version)
        version.title = payload["title"]
        version.slug = payload["slug"]
        version.status = CourseVersionStatus.PUBLISHED
        version.unlock_mode = payload["unlock_mode"]
        version.final_test_id = int(payload["final_test_id"]) if payload.get("final_test_id") else None
        version.final_pass_mark = payload["final_pass_mark"]
        version.final_test_attempts = payload["final_test_attempts"]
        version.final_test_cooldown_days = payload["final_test_cooldown_days"]
        await self.db.flush()

        for module_data in payload["modules"]:
            module_id = int(module_data["module_id"])
            module = await self.db.get(ModuleRef, module_id)
            if module is None:
                module = ModuleRef(module_id=module_id, version_id=version_id, position=module_data["position"], pass_mark=module_data["pass_mark"])
                self.db.add(module)
            module.title = module_data["title"]
            module.position = module_data["position"]
            module.pass_mark = module_data["pass_mark"]
            module.module_test_id = int(module_data["module_test_id"]) if module_data.get("module_test_id") else None
            await self.db.flush()

            for topic_data in module_data["topics"]:
                topic_id = int(topic_data["topic_id"])
                topic = await self.db.get(TopicRef, topic_id)
                if topic is None:
                    topic = TopicRef(topic_id=topic_id, module_id=module_id, position=topic_data["position"], pass_mark=topic_data["pass_mark"])
                    self.db.add(topic)
                topic.title = topic_data["title"]
                topic.position = topic_data["position"]
                topic.pass_mark = topic_data["pass_mark"]
                topic.topic_test_id = int(topic_data["topic_test_id"]) if topic_data.get("topic_test_id") else None
                await self.db.flush()

                for item_data in topic_data["items"]:
                    item_id = int(item_data["topic_item_id"])
                    item = await self.db.get(TopicItemRef, item_id)
                    if item is None:
                        item = TopicItemRef(topic_item_id=item_id, topic_id=topic_id, position=item_data["position"], item_type=item_data["item_type"], required=item_data["required"])
                        self.db.add(item)
                    item.title = item_data["title"]
                    item.position = item_data["position"]
                    item.item_type = item_data["item_type"]
                    item.required = item_data["required"]

    async def mark_retired(self, payload: dict[str, Any]) -> None:
        version_id = int(payload["version_id"])
        version = await self.db.get(CourseVersionRef, version_id)
        if version is not None:
            version.status = CourseVersionStatus.RETIRED

    async def get_latest_published_for_course(self, course_id: int) -> CourseVersionRef:
        """A course can have several published versions at once (subscriptions choose their
        own upgrade policy, see docs/PRODUCT.md §3.2); a new batch always starts on the latest."""
        version = (
            await self.db.execute(
                select(CourseVersionRef)
                .where(CourseVersionRef.course_id == course_id, CourseVersionRef.status == CourseVersionStatus.PUBLISHED)
                .order_by(CourseVersionRef.version_id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if version is None:
            raise NotFoundError("No published version of this course was found.", code="COURSE_NOT_AVAILABLE")
        return version

    async def get_full_tree(self, version_id: int) -> CourseVersionRef:
        version = (
            await self.db.execute(
                select(CourseVersionRef).where(CourseVersionRef.version_id == version_id).options(_LOAD_TREE)
            )
        ).scalar_one_or_none()
        if version is None:
            raise NotFoundError("Course version not found.", code="COURSE_VERSION_NOT_FOUND")
        return version
