from datetime import UTC, datetime

from lms_common.events import Event

from app.core.ids import new_public_id
from app.db.session import build_engine, build_sessionmaker
from app.events.consumers.router import dispatch
from app.models import Base
from app.models.media_asset import MediaAsset
from tests.conftest import _settings


def _event(event_type: str, payload: dict) -> Event:
    return Event(event_id="evt-1", event_type=event_type, aggregate_type="course", occurred_time=datetime.now(UTC), payload=payload)


async def test_course_retired_archives_tagged_assets() -> None:
    settings = _settings()
    engine = build_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = build_sessionmaker(engine)

    async with sessionmaker() as db:
        tagged = MediaAsset(
            public_id=new_public_id(), kind="video", original_filename="a.mp4", content_type="video/mp4",
            storage_key="k1", context_type="course_version", context_id=1755000000009999, created_by=1,
        )
        other = MediaAsset(
            public_id=new_public_id(), kind="video", original_filename="b.mp4", content_type="video/mp4",
            storage_key="k2", context_type="course_version", context_id=1755000000000001, created_by=1,
        )
        db.add_all([tagged, other])
        await db.commit()

        await dispatch(db, settings, _event("course.retired", {"course_id": "1", "version_id": "1755000000009999"}))

        refreshed_tagged = await db.get(MediaAsset, tagged.id)
        refreshed_other = await db.get(MediaAsset, other.id)
        assert refreshed_tagged.archived_at is not None
        assert refreshed_other.archived_at is None

    await engine.dispose()


async def test_unknown_event_type_is_ignored() -> None:
    settings = _settings()
    engine = build_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = build_sessionmaker(engine)
    async with sessionmaker() as db:
        await dispatch(db, settings, _event("user.created", {"user_id": "1"}))  # must not raise
    await engine.dispose()
