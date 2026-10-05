from lms_common.events import Event

from app.core.ids import new_public_id
from app.db.session import build_engine, build_sessionmaker
from app.events.consumers.media_events import dispatch
from app.models import Base
from app.models.course import Course
from app.models.course_rule import CourseRule
from app.models.course_version import CourseVersion
from app.models.module import Module
from app.models.topic import Topic
from app.models.topic_item import TopicItem
from tests.conftest import _settings


def _event(event_type: str, payload: dict) -> Event:
    from datetime import UTC, datetime

    return Event(event_id="evt-1", event_type=event_type, aggregate_type="media", occurred_time=datetime.now(UTC), payload=payload)


async def test_media_ready_marks_the_topic_item_ready() -> None:
    engine = build_engine(_settings())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = build_sessionmaker(engine)

    async with sessionmaker() as db:
        course = Course(public_id=new_public_id(), title="C", slug="c-1", summary="A summary of ten chars.", created_by=1)
        db.add(course)
        await db.flush()
        version = CourseVersion(public_id=new_public_id(), course_id=course.id, version_number=1, created_by=1)
        db.add(version)
        await db.flush()
        db.add(CourseRule.with_defaults(version.id))
        module = Module(public_id=new_public_id(), course_version_id=version.id, title="M", position=1, pass_mark=60)
        db.add(module)
        await db.flush()
        topic = Topic(public_id=new_public_id(), module_id=module.id, title="T", position=1, pass_mark=60)
        db.add(topic)
        await db.flush()
        item = TopicItem(
            public_id=new_public_id(), topic_id=topic.id, item_type="video", title="Intro", position=1, media_id=999
        )
        db.add(item)
        await db.commit()
        item_public_id = item.public_id

        await dispatch(db, _event("media.ready", {"topic_item_id": str(item_public_id), "duration_seconds": 300}))
        await db.commit()

        refreshed = await db.get(TopicItem, item.id)
        assert refreshed.media_ready is True
        assert refreshed.duration_seconds == 300

    await engine.dispose()


async def test_test_published_attaches_module_and_topic_tests_and_ignores_other_targets() -> None:
    """assessment-service publishes every kind of test; only module and topic tests belong on a catalog row (a final
    test is chosen on the course rule, and a topic id must never be looked up with a course's id)."""
    engine = build_engine(_settings())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = build_sessionmaker(engine)

    async with sessionmaker() as db:
        course = Course(public_id=new_public_id(), title="C", slug="c-2", summary="A summary of ten chars.", created_by=1)
        db.add(course)
        await db.flush()
        version = CourseVersion(public_id=new_public_id(), course_id=course.id, version_number=1, created_by=1)
        db.add(version)
        await db.flush()
        db.add(CourseRule.with_defaults(version.id))
        module = Module(public_id=new_public_id(), course_version_id=version.id, title="M", position=1, pass_mark=60)
        db.add(module)
        await db.flush()
        topic = Topic(public_id=new_public_id(), module_id=module.id, title="T", position=1, pass_mark=60)
        db.add(topic)
        await db.commit()

        full = {"title": "T", "kind": "module", "pass_mark_percent": 60, "total_marks": 10.0}  # the fields it also carries
        await dispatch(db, _event("test.published", {**full, "target_type": "module", "target_id": str(module.public_id), "test_id": "1755000000000222"}))
        await dispatch(db, _event("test.published", {**full, "target_type": "topic", "target_id": str(topic.public_id), "test_id": "1755000000000333"}))
        # a final test targets a course, and a practice test has no target: neither may touch a topic or module
        await dispatch(db, _event("test.published", {**full, "target_type": "course", "target_id": str(topic.public_id), "test_id": "1755000000000444"}))
        await dispatch(db, _event("test.published", {**full, "target_type": None, "target_id": None, "test_id": "1755000000000555"}))
        await db.commit()

        assert (await db.get(Module, module.id)).module_test_id == 1755000000000222
        assert (await db.get(Topic, topic.id)).topic_test_id == 1755000000000333
    await engine.dispose()


async def test_unknown_event_type_is_ignored() -> None:
    engine = build_engine(_settings())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = build_sessionmaker(engine)
    async with sessionmaker() as db:
        await dispatch(db, _event("user.created", {"user_id": "1"}))  # must not raise
    await engine.dispose()
