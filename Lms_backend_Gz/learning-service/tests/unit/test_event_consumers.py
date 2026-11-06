from datetime import UTC, datetime

from lms_common.events import Event

from app.db.session import build_engine, build_sessionmaker
from app.domain.enums import CourseVersionStatus, InstitutionStatus
from app.events.consumers.router import dispatch
from app.models import Base
from app.models.course_version_ref import CourseVersionRef
from app.models.institution_ref import InstitutionRef
from app.models.module_ref import ModuleRef
from tests.conftest import _settings, published_course_payload


def _event(event_type: str, payload: dict) -> Event:
    return Event(event_id="evt-1", event_type=event_type, aggregate_type="test", occurred_time=datetime.now(UTC), payload=payload)


async def test_institution_created_then_suspended_updates_the_local_ref() -> None:
    engine = build_engine(_settings())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = build_sessionmaker(engine)

    async with sessionmaker() as db:
        await dispatch(db, _event("institution.created", {"organization_id": "1", "name": "A School", "code": "A-1", "status": "active"}))
        await db.commit()
        assert (await db.get(InstitutionRef, 1)).status == InstitutionStatus.ACTIVE

        await dispatch(db, _event("institution.suspended", {"organization_id": "1", "name": "A School", "code": "A-1", "status": "suspended"}))
        await db.commit()
        assert (await db.get(InstitutionRef, 1)).status == InstitutionStatus.SUSPENDED

    await engine.dispose()


async def test_course_published_builds_the_full_local_tree() -> None:
    engine = build_engine(_settings())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = build_sessionmaker(engine)

    payload = published_course_payload()
    async with sessionmaker() as db:
        await dispatch(db, _event("course.published", payload))
        await db.commit()

        version = await db.get(CourseVersionRef, int(payload["version_id"]))
        assert version.status == CourseVersionStatus.PUBLISHED
        assert version.title == "A Course"
        module = await db.get(ModuleRef, payload["modules"][0]["module_id"])
        assert module.pass_mark == 60

        await dispatch(db, _event("course.retired", payload))
        await db.commit()
        version = await db.get(CourseVersionRef, int(payload["version_id"]))
        assert version.status == CourseVersionStatus.RETIRED

    await engine.dispose()


async def test_unknown_event_type_is_ignored() -> None:
    engine = build_engine(_settings())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = build_sessionmaker(engine)
    async with sessionmaker() as db:
        await dispatch(db, _event("user.created", {"user_id": "1"}))  # must not raise
    await engine.dispose()
