"""Self-registered learners: bought access enrols them in their course's learner batch; expiry withdraws them."""

from sqlalchemy import select

from app.events.consumers.router import dispatch
from app.models.batch import Batch
from app.models.enrollment import Enrollment
from app.models.outbox_event import OutboxEvent
from tests.conftest import TEST_COURSE_ID, TEST_ORG_ID

LEARNER, OTHER = 1755000000241001, 1755000000241002


class _Event:
    def __init__(self, event_type: str, payload: dict) -> None:
        self.event_type, self.payload = event_type, payload


def _access(kind: str, user: int = LEARNER) -> _Event:
    return _Event(
        f"course_access.{kind}",
        {"access_id": "1755000000241900", "user_id": str(user), "organization_id": str(TEST_ORG_ID), "course_id": str(TEST_COURSE_ID),
         "starts_at": "2026-10-20T10:00:00Z", "ends_at": "2027-10-20T10:00:00Z"},
    )


async def _apply(app, event: _Event) -> None:
    async with app.state.sessionmaker() as db:
        await dispatch(db, event)  # type: ignore[arg-type]
        await db.commit()


async def _rows(app, model):
    async with app.state.sessionmaker() as db:
        return list((await db.execute(select(model))).scalars())


async def test_bought_access_enrols_the_learner_once_and_expiry_withdraws_them(app, client, seed_institution, seed_course, as_student, as_institution_head) -> None:
    await seed_institution()
    await seed_course()
    await _apply(app, _access("granted"))
    await _apply(app, _access("extended"))  # still active: nothing new
    await _apply(app, _access("granted", OTHER))

    batches = await _rows(app, Batch)
    assert len(batches) == 1 and batches[0].subscription_id == 0  # one learner batch per course
    enrollments = await _rows(app, Enrollment)
    assert sorted(e.student_user_id for e in enrollments) == [LEARNER, OTHER] and all(e.status == "active" for e in enrollments)

    as_student(user_id=LEARNER)
    mine = (await client.get("/api/v1/enrollments")).json()["enrollments"]
    assert len(mine) == 1

    await _apply(app, _access("expired"))
    await _apply(app, _access("expired"))  # redelivered: once only
    statuses = {e.student_user_id: e.status for e in await _rows(app, Enrollment)}
    assert statuses == {LEARNER: "withdrawn", OTHER: "active"}
    removed = [e for e in await _rows(app, OutboxEvent) if e.event_type == "enrollment.removed"]
    assert len(removed) == 1 and removed[0].payload["reason"] == "access_expired"

    await _apply(app, _access("granted"))  # bought again
    active = [e for e in await _rows(app, Enrollment) if e.student_user_id == LEARNER and e.status == "active"]
    assert len(active) == 1


async def test_nobody_hand_enrols_into_a_learner_batch(app, client, seed_institution, seed_course, as_admin) -> None:
    await seed_institution()
    await seed_course()
    await _apply(app, _access("granted"))
    batch = (await _rows(app, Batch))[0]
    as_admin()
    response = await client.post(f"/api/v1/batches/{batch.public_id}/enrollments", json={"student_user_id": str(OTHER)})
    assert response.status_code == 400 and response.json()["code"] == "LEARNER_BATCH"
