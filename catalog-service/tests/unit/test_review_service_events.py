"""Outbox event payloads must carry the course's PUBLIC id (see lms-backend/README.md §4:
"payload is JSON with public ids only") — regression guard for a bug where the internal
UUID foreign key was sent instead."""

from sqlalchemy import select

from app.core.ids import new_public_id
from app.db.session import build_engine, build_sessionmaker
from app.domain.enums import ContentStatus
from app.models import Base
from app.models.course import Course
from app.models.course_rule import CourseRule
from app.models.course_version import CourseVersion
from app.models.module import Module
from app.models.outbox_event import OutboxEvent
from app.models.topic import Topic
from app.models.topic_item import TopicItem
from app.services.review_service import ReviewService
from tests.conftest import _settings


async def test_course_published_event_carries_the_public_course_id() -> None:
    engine = build_engine(_settings())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = build_sessionmaker(engine)

    async with sessionmaker() as db:
        course = Course(public_id=new_public_id(), title="A Course", slug="a-course", summary="Ten characters plus.", created_by=1)
        db.add(course)
        await db.flush()
        version = CourseVersion(
            public_id=new_public_id(), course_id=course.id, version_number=1, status=ContentStatus.IN_REVIEW, created_by=1
        )
        db.add(version)
        await db.flush()
        db.add(CourseRule.with_defaults(version.id))
        module = Module(public_id=new_public_id(), course_version_id=version.id, title="M", position=1, pass_mark=60)
        db.add(module)
        await db.flush()
        topic = Topic(public_id=new_public_id(), module_id=module.id, title="T", position=1, pass_mark=60)
        db.add(topic)
        await db.flush()
        db.add(TopicItem(public_id=new_public_id(), topic_id=topic.id, item_type="notes", title="N", position=1, content_text="x"))
        await db.commit()

        await ReviewService(db).approve(version, actor_user_id=1)

        event = (
            await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == "course.published"))
        ).scalar_one()
        assert event.payload["course_id"] == str(course.public_id)
        assert event.payload["title"] == "A Course"
        assert event.payload["slug"] == "a-course"

        # course.published carries the full authoring tree (see ReviewService._published_structure_payload):
        # a consumer like learning-service builds its unlock-rule read-model purely from this event.
        assert event.payload["unlock_mode"] == "sequential"
        assert len(event.payload["modules"]) == 1
        module_payload = event.payload["modules"][0]
        assert module_payload["pass_mark"] == 60
        assert len(module_payload["topics"]) == 1
        topic_payload = module_payload["topics"][0]
        assert len(topic_payload["items"]) == 1
        assert topic_payload["items"][0]["item_type"] == "notes"
        # ai-tutor-service indexes course content from these additive fields.
        assert (module_payload["title"], topic_payload["title"]) == ("M", "T")
        item_payload = topic_payload["items"][0]
        assert item_payload["title"] == "N" and item_payload["content_text"] == "x" and item_payload["media_id"] is None

    await engine.dispose()
