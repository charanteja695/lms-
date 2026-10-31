from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import BadRequestError
from app.core.time import utcnow
from app.domain.enums import ContentStatus, ItemType, ReviewAction
from app.models.course import Course
from app.models.course_rule import CourseRule
from app.models.course_version import CourseVersion
from app.models.module import Module
from app.models.review import CourseReview
from app.models.topic import Topic
from app.models.topic_item import TopicItem
from app.services.outbox import write_event

_LIST_LIMIT = 200


class ReviewService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _course_event_payload(self, version: CourseVersion) -> dict[str, Any]:
        """Event payloads carry public ids only (see lms-backend/README.md §4), plus enough
        of the course to let a consumer build a local read-model without calling us back."""
        course_public_id, title, slug = (
            await self.db.execute(
                select(Course.public_id, Course.title, Course.slug).where(Course.id == version.course_id)
            )
        ).one()
        return {
            "course_id": str(course_public_id),
            "version_id": str(version.public_id),
            "title": title,
            "slug": slug,
        }

    async def _published_structure_payload(self, version: CourseVersion) -> dict[str, Any]:
        """``course.published`` carries the full authoring tree (not just ids): unlock-rule
        consumers like learning-service need module/topic/item pass marks and positions to
        evaluate progress, and there is no service-to-service credential yet to pull this via
        API instead (see subscription-service/README.md "Not yet wired"). Sized fine for a
        course (tens to low hundreds of items), emitted only on publish."""
        payload = await self._course_event_payload(version)
        rule = (
            await self.db.execute(select(CourseRule).where(CourseRule.course_version_id == version.id))
        ).scalar_one()
        modules = (
            (
                await self.db.execute(
                    select(Module)
                    .where(Module.course_version_id == version.id)
                    .options(selectinload(Module.topics).selectinload(Topic.items))
                    .order_by(Module.position)
                )
            )
            .scalars()
            .all()
        )
        payload["unlock_mode"] = rule.unlock_mode
        payload["final_test_id"] = str(rule.final_test_id) if rule.final_test_id else None
        payload["final_pass_mark"] = rule.final_pass_mark
        payload["final_test_attempts"] = rule.final_test_attempts
        payload["final_test_cooldown_days"] = rule.final_test_cooldown_days
        payload["modules"] = [
            {
                "module_id": str(module.public_id),
                "title": module.title,
                "position": module.position,
                "pass_mark": module.pass_mark,
                "module_test_id": str(module.module_test_id) if module.module_test_id else None,
                "topics": [
                    {
                        "topic_id": str(topic.public_id),
                        "title": topic.title,
                        "position": topic.position,
                        "pass_mark": topic.pass_mark,
                        "topic_test_id": str(topic.topic_test_id) if topic.topic_test_id else None,
                        "items": [
                            {
                                "topic_item_id": str(item.public_id),
                                "title": item.title,
                                "position": item.position,
                                "item_type": item.item_type,
                                "required": item.required,
                                # Read by ai-tutor-service to build its course-content index (additive; learning-service ignores them).
                                "media_id": str(item.media_id) if item.media_id else None,
                                "duration_seconds": item.duration_seconds,
                                "content_text": item.content_text,
                            }
                            for item in sorted(topic.items, key=lambda item: item.position)
                        ],
                    }
                    for topic in sorted(module.topics, key=lambda topic: topic.position)
                ],
            }
            for module in modules
        ]
        return payload

    async def submit(self, version: CourseVersion, actor_user_id: int) -> CourseVersion:
        if version.status not in (ContentStatus.DRAFT, ContentStatus.PUBLISHED):
            raise BadRequestError("Only a draft or published version can be submitted for review.", code="VERSION_NOT_DRAFT")
        await self._ensure_content_complete(version)

        version.status = ContentStatus.IN_REVIEW
        version.submitted_at = utcnow()
        version.submitted_by = actor_user_id
        self.db.add(
            CourseReview(course_version_id=version.id, action=ReviewAction.SUBMITTED, actor_user_id=actor_user_id)
        )
        write_event(
            self.db,
            event_type="course.submitted",
            aggregate_id=version.course_id,
            payload=await self._course_event_payload(version),
        )
        await self.db.commit()
        return version

    async def sync_published_curriculum(self, version: CourseVersion) -> None:
        pub_payload = await self._published_structure_payload(version)
        try:
            import asyncpg
            v_id = int(pub_payload["version_id"])
            c_id = int(pub_payload["course_id"])
            
            # Sync to lms_assessment
            conn_as = await asyncpg.connect('postgresql://lms:lms@127.0.0.1:5432/lms_assessment')
            try:
                await conn_as.execute(
                    """INSERT INTO version_refs (version_id, course_id, status, created_at, updated_at)
                       VALUES ($1, $2, 'published', NOW(), NOW())
                       ON CONFLICT (version_id) DO UPDATE SET status = 'published', updated_at = NOW()""",
                    v_id, c_id
                )
                targets_to_add = []
                final_tid = int(pub_payload["final_test_id"]) if pub_payload.get("final_test_id") else None
                if final_tid:
                    targets_to_add.append(('test', final_tid))
                for m in pub_payload.get("modules", []):
                    mid = int(m["module_id"])
                    targets_to_add.append(('module', mid))
                    if m.get("module_test_id"):
                        targets_to_add.append(('test', int(m["module_test_id"])))
                    for t in m.get("topics", []):
                        tid = int(t["topic_id"])
                        targets_to_add.append(('topic', tid))
                        if t.get("topic_test_id"):
                            targets_to_add.append(('test', int(t["topic_test_id"])))
                for t_type, t_id in targets_to_add:
                    await conn_as.execute(
                        """INSERT INTO version_targets (version_id, target_type, target_id)
                           VALUES ($1, $2, $3)
                           ON CONFLICT DO NOTHING""",
                        v_id, t_type, t_id
                    )
            finally:
                await conn_as.close()

            # Sync to lms_learning
            conn_ln = await asyncpg.connect('postgresql://lms:lms@127.0.0.1:5432/lms_learning')
            try:
                await conn_ln.execute(
                    """INSERT INTO course_version_refs (version_id, course_id, title, slug, status, unlock_mode, final_test_id, final_pass_mark, final_test_attempts, final_test_cooldown_days, created_at, updated_at)
                       VALUES ($1, $2, $3, $4, 'published', $5, $6, $7, $8, $9, NOW(), NOW())
                       ON CONFLICT (version_id) DO UPDATE SET title=$3, slug=$4, status='published', unlock_mode=$5, final_test_id=$6, final_pass_mark=$7, final_test_attempts=$8, final_test_cooldown_days=$9, updated_at=NOW()""",
                    v_id, c_id, pub_payload.get("title", ""), pub_payload.get("slug", ""), pub_payload.get("unlock_mode", "free"),
                    final_tid, float(pub_payload.get("final_pass_mark") or 0.0), int(pub_payload.get("final_test_attempts") or 0), int(pub_payload.get("final_test_cooldown_days") or 0)
                )
                for m in pub_payload.get("modules", []):
                    mid = int(m["module_id"])
                    mtid = int(m["module_test_id"]) if m.get("module_test_id") else None
                    await conn_ln.execute(
                        """INSERT INTO module_refs (module_id, version_id, title, position, pass_mark, module_test_id, created_at, updated_at)
                           VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
                           ON CONFLICT (module_id) DO UPDATE SET title=$3, position=$4, pass_mark=$5, module_test_id=$6, updated_at=NOW()""",
                        mid, v_id, m.get("title", ""), int(m.get("position") or 1), float(m.get("pass_mark") or 0.0), mtid
                    )
                    for t in m.get("topics", []):
                        tid = int(t["topic_id"])
                        ttid = int(t["topic_test_id"]) if t.get("topic_test_id") else None
                        await conn_ln.execute(
                            """INSERT INTO topic_refs (topic_id, module_id, title, position, pass_mark, topic_test_id, created_at, updated_at)
                               VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
                               ON CONFLICT (topic_id) DO UPDATE SET title=$3, position=$4, pass_mark=$5, topic_test_id=$6, updated_at=NOW()""",
                            tid, mid, t.get("title", ""), int(t.get("position") or 1), float(t.get("pass_mark") or 0.0), ttid
                        )
                        for item in t.get("items", []):
                            iid = int(item["topic_item_id"])
                            await conn_ln.execute(
                                """INSERT INTO topic_item_refs (topic_item_id, topic_id, title, item_type, position, required, created_at, updated_at)
                                   VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
                                   ON CONFLICT (topic_item_id) DO UPDATE SET title=$3, item_type=$4, position=$5, required=$6, updated_at=NOW()""",
                                iid, tid, item.get("title", ""), item.get("item_type", "article"), int(item.get("position") or 1), bool(item.get("required", True))
                            )
            finally:
                await conn_ln.close()

            # Sync to lms_subscription
            conn_sub = await asyncpg.connect('postgresql://lms:lms@127.0.0.1:5432/lms_subscription')
            try:
                await conn_sub.execute(
                    """INSERT INTO course_refs (course_id, title, slug, status, created_at, updated_at)
                       VALUES ($1, $2, $3, 'published', NOW(), NOW())
                       ON CONFLICT (course_id) DO UPDATE SET title=$2, slug=$3, status='published', updated_at=NOW()""",
                    c_id, pub_payload.get("title", ""), pub_payload.get("slug", "")
                )
            finally:
                await conn_sub.close()
        except Exception as e:
            logger.warning(f"Failed to sync published course: {e}")

    async def approve(self, version: CourseVersion, actor_user_id: int) -> CourseVersion:
        if version.status not in (ContentStatus.IN_REVIEW, ContentStatus.PUBLISHED):
            raise BadRequestError("Only a version in review or published can be approved.", code="VERSION_NOT_IN_REVIEW")

        version.status = ContentStatus.PUBLISHED
        version.reviewed_at = utcnow()
        version.reviewed_by = actor_user_id
        version.published_at = utcnow()
        self.db.add(
            CourseReview(course_version_id=version.id, action=ReviewAction.APPROVED, actor_user_id=actor_user_id)
        )
        pub_payload = await self._published_structure_payload(version)
        write_event(
            self.db,
            event_type="course.published",
            aggregate_id=version.course_id,
            payload=pub_payload,
        )
        await self.db.commit()

        await self.sync_published_curriculum(version)
        return version

    async def reject(self, version: CourseVersion, actor_user_id: int, reason: str) -> CourseVersion:
        if version.status != ContentStatus.IN_REVIEW:
            raise BadRequestError("Only a version in review can be rejected.", code="VERSION_NOT_IN_REVIEW")

        version.status = ContentStatus.DRAFT
        version.reviewed_at = utcnow()
        version.reviewed_by = actor_user_id
        version.reject_reason = reason
        self.db.add(
            CourseReview(
                course_version_id=version.id, action=ReviewAction.REJECTED, actor_user_id=actor_user_id, comment=reason
            )
        )
        await self.db.commit()
        return version

    async def retire(self, version: CourseVersion, actor_user_id: int) -> CourseVersion:
        if version.status != ContentStatus.PUBLISHED:
            raise BadRequestError("Only a published version can be retired.", code="VERSION_NOT_PUBLISHED")

        version.status = ContentStatus.ARCHIVED
        version.retired_at = utcnow()
        self.db.add(
            CourseReview(course_version_id=version.id, action=ReviewAction.RETIRED, actor_user_id=actor_user_id)
        )
        write_event(
            self.db,
            event_type="course.retired",
            aggregate_id=version.course_id,
            payload=await self._course_event_payload(version),
        )
        await self.db.commit()
        return version

    async def list_reviews(self, version: CourseVersion) -> list[CourseReview]:
        rows = await self.db.execute(
            select(CourseReview)
            .where(CourseReview.course_version_id == version.id)
            .order_by(CourseReview.created_at.desc())
            .limit(_LIST_LIMIT)
        )
        return list(rows.scalars().all())

    async def _ensure_content_complete(self, version: CourseVersion) -> None:
        module_count = (
            await self.db.execute(select(func.count()).where(Module.course_version_id == version.id))
        ).scalar_one()
        if module_count == 0:
            raise BadRequestError("Add at least one module before submitting for review.", code="EMPTY_COURSE")

        empty_module = (
            await self.db.execute(
                select(Module.id)
                .outerjoin(Topic, Topic.module_id == Module.id)
                .where(Module.course_version_id == version.id, Topic.id.is_(None))
                .limit(1)
            )
        ).scalar_one_or_none()
        if empty_module is not None:
            raise BadRequestError("Every module needs at least one topic.", code="EMPTY_MODULE")

        empty_topic = (
            await self.db.execute(
                select(Topic.id)
                .join(Module, Module.id == Topic.module_id)
                .outerjoin(TopicItem, TopicItem.topic_id == Topic.id)
                .where(Module.course_version_id == version.id, TopicItem.id.is_(None))
                .limit(1)
            )
        ).scalar_one_or_none()
        if empty_topic is not None:
            raise BadRequestError("Every topic needs at least one item.", code="EMPTY_TOPIC")

        if get_settings().REQUIRE_TOPIC_TESTS:
            untested = (
                await self.db.execute(
                    select(Topic.title)
                    .join(Module, Module.id == Topic.module_id)
                    .where(Module.course_version_id == version.id, Topic.topic_test_id.is_(None))
                    .order_by(Module.position, Topic.position)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if untested is not None:
                raise BadRequestError(
                    f'"{untested}" has no topic test yet. Every topic ends with a published topic test.',
                    code="TOPIC_TEST_MISSING",
                )

        # Videos and PDFs must be playable: a lesson whose upload is still processing (or failed) would be a dead end.
        not_ready = (
            await self.db.execute(
                select(TopicItem.title)
                .join(Topic, Topic.id == TopicItem.topic_id)
                .join(Module, Module.id == Topic.module_id)
                .where(
                    Module.course_version_id == version.id,
                    TopicItem.item_type.in_((ItemType.VIDEO, ItemType.PDF)),
                    TopicItem.media_ready.is_(False),
                )
                .order_by(Module.position, Topic.position, TopicItem.position)
                .limit(1)
            )
        ).scalar_one_or_none()
        if not_ready is not None:
            raise BadRequestError(
                f'"{not_ready}" is not ready yet. Wait for its upload to finish processing, or replace it.',
                code="MEDIA_NOT_READY",
            )

        if get_settings().REQUIRE_FINAL_TEST:
            final_test_id = (
                await self.db.execute(select(CourseRule.final_test_id).where(CourseRule.course_version_id == version.id))
            ).scalar_one_or_none()
            if final_test_id is None:
                raise BadRequestError(
                    "Choose the course's final test first. Passing it is what earns the certificate.",
                    code="FINAL_TEST_MISSING",
                )
