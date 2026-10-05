from datetime import UTC, datetime

from lms_common.events import Event

from app.db.session import build_engine, build_sessionmaker
from app.domain.enums import InstitutionStatus
from app.events.consumers.router import dispatch
from app.models import Base
from app.models.course_ref import CourseRef
from app.models.institution_ref import InstitutionRef
from tests.conftest import _settings


def _event(event_type: str, payload: dict) -> Event:
    return Event(event_id="evt-1", event_type=event_type, aggregate_type="institution", occurred_time=datetime.now(UTC), payload=payload)


async def test_institution_created_then_suspended_updates_the_local_ref() -> None:
    engine = build_engine(_settings())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = build_sessionmaker(engine)

    async with sessionmaker() as db:
        await dispatch(db, _event("institution.created", {"organization_id": "1", "name": "A School", "code": "A-1", "status": "active"}))
        await db.commit()
        ref = await db.get(InstitutionRef, 1)
        assert ref.status == InstitutionStatus.ACTIVE

        await dispatch(db, _event("institution.suspended", {"organization_id": "1", "name": "A School", "code": "A-1", "status": "suspended"}))
        await db.commit()
        ref = await db.get(InstitutionRef, 1)
        assert ref.status == InstitutionStatus.SUSPENDED

    await engine.dispose()


async def test_course_published_then_retired_updates_the_local_ref() -> None:
    engine = build_engine(_settings())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = build_sessionmaker(engine)

    async with sessionmaker() as db:
        await dispatch(db, _event("course.published", {"course_id": "1", "title": "A Course", "slug": "a-course"}))
        await db.commit()
        ref = await db.get(CourseRef, 1)
        assert ref.status == "published"

        await dispatch(db, _event("course.retired", {"course_id": "1", "title": "A Course", "slug": "a-course"}))
        await db.commit()
        ref = await db.get(CourseRef, 1)
        assert ref.status == "retired"

    await engine.dispose()


async def test_unknown_event_type_is_ignored() -> None:
    engine = build_engine(_settings())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = build_sessionmaker(engine)
    async with sessionmaker() as db:
        await dispatch(db, _event("user.created", {"user_id": "1"}))  # must not raise
    await engine.dispose()
