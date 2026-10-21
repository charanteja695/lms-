"""A learner's bought access: granted, extended by a repeat purchase, applied once per purchase, expired by the sweep."""

from datetime import timedelta

from sqlalchemy import select

from app.core.time import utcnow
from app.events.consumers.router import dispatch
from app.models.course_access import CourseAccess
from app.models.outbox_event import OutboxEvent
from app.services.course_access_service import CourseAccessService

LEARNER, OTHER, ORG, COURSE = 1755000000231001, 1755000000231002, 1755000000231100, 1755000000231200


class _Event:
    def __init__(self, event_type: str, payload: dict) -> None:
        self.event_type, self.payload = event_type, payload


def _purchase(purchase_id: int, *, user: int = LEARNER, days: int = 30) -> _Event:
    return _Event(
        "course.purchased",
        {"purchase_id": str(purchase_id), "organization_id": str(ORG), "user_id": str(user), "course_id": str(COURSE), "valid_days": days, "amount": 100, "occurred_at": "2026-10-20T10:00:00Z"},
    )


async def _events(app, kind: str) -> list[dict]:
    async with app.state.sessionmaker() as db:
        return [e.payload for e in (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == kind))).scalars()]


async def _apply(app, event: _Event) -> None:
    async with app.state.sessionmaker() as db:
        await dispatch(db, event)  # type: ignore[arg-type]
        await db.commit()


async def test_a_purchase_grants_access_a_repeat_extends_it_and_a_replay_changes_nothing(app, client, authed) -> None:
    await _apply(app, _purchase(1, days=30))
    await _apply(app, _purchase(1, days=30))  # the stream redelivered it
    granted = await _events(app, "course_access.granted")
    assert len(granted) == 1 and granted[0]["user_id"] == str(LEARNER) and granted[0]["course_id"] == str(COURSE)

    await _apply(app, _purchase(2, days=30))
    extended = await _events(app, "course_access.extended")
    assert len(extended) == 1
    async with app.state.sessionmaker() as db:
        access = (await db.execute(select(CourseAccess))).scalar_one()
        assert (access.ends_at - access.starts_at).days == 60

    authed(user_id=LEARNER, role="student", organization_id=ORG)
    mine = (await client.get("/api/v1/me/course-access")).json()["course_access"]
    assert [(a["course_id"], a["status"]) for a in mine] == [(str(COURSE), "active")]
    authed(user_id=OTHER, role="student", organization_id=ORG)
    assert (await client.get("/api/v1/me/course-access")).json()["course_access"] == []


async def test_access_expires_when_its_time_runs_out_and_buying_again_reopens_it(app) -> None:
    await _apply(app, _purchase(1, days=30))
    async with app.state.sessionmaker() as db:
        access = (await db.execute(select(CourseAccess))).scalar_one()
        access.ends_at = utcnow() - timedelta(minutes=1)
        await db.commit()
    async with app.state.sessionmaker() as db:
        assert await CourseAccessService(db).expire_due() == 1
    async with app.state.sessionmaker() as db:
        assert await CourseAccessService(db).expire_due() == 0  # announced once
    assert len(await _events(app, "course_access.expired")) == 1

    await _apply(app, _purchase(2, days=15))
    regranted = await _events(app, "course_access.granted")
    assert len(regranted) == 2
    async with app.state.sessionmaker() as db:
        access = (await db.execute(select(CourseAccess))).scalar_one()
        assert access.status == "active" and access.ends_at > utcnow() + timedelta(days=14)
