"""Topic and module tests gate completion: items done AND test passed (docs/PRODUCT.md §3.1), from assessment-service's
``attempt.finalized``."""

from collections import Counter
from datetime import UTC, datetime

from httpx import AsyncClient
from lms_common.events import Event
from sqlalchemy import select

from app.events.consumers.router import dispatch
from app.models.outbox_event import OutboxEvent
from tests.conftest import published_course_payload
from tests.integration.test_enrollment_and_progress import STUDENT_ID, _batch

TOPIC_TEST, MODULE_TEST = 1755000000000777, 1755000000000888
ITEMS = (1755000000005301, 1755000000005302)


async def _send(app, event_type: str, payload: dict, event_id: str = "evt") -> None:
    event = Event(event_id=event_id, event_type=event_type, aggregate_type="attempt", occurred_time=datetime.now(UTC), payload=payload)
    async with app.state.sessionmaker() as db:
        await dispatch(db, event)
        await db.commit()


def _finalized(enrollment_id: str, test_id: int, kind: str, result: str, *, attempt_id: int = 1755000000006001, revision: int = 1) -> dict:
    return {
        "enrollment_id": enrollment_id, "test_id": str(test_id), "test_kind": kind, "result": result,
        "percent": 80.0 if result == "passed" else 30.0, "attempt_id": str(attempt_id), "revision": revision,
    }


async def _events(app) -> Counter:
    async with app.state.sessionmaker() as db:
        return Counter(e.event_type for e in (await db.execute(select(OutboxEvent))).scalars())


async def _state(client: AsyncClient, enrollment: dict) -> dict:
    return (await client.get(f"/api/v1/enrollments/{enrollment['enrollment_id']}/unlock-state")).json()["unlock_state"]


async def _enrolled_with_tests(client, app, as_institution_head, as_student, seed_institution, seed_course, seed_entitlement) -> dict:
    batch = await _batch(client, as_institution_head, seed_institution, seed_course, seed_entitlement)
    payload = published_course_payload()  # the version now names its tests, as catalog's course.published would
    payload["modules"][0]["module_test_id"] = str(MODULE_TEST)
    payload["modules"][0]["topics"][0]["topic_test_id"] = str(TOPIC_TEST)
    await _send(app, "course.published", payload)
    as_institution_head()
    enrollment = (await client.post(f"/api/v1/batches/{batch['batch_id']}/enrollments", json={"student_user_id": str(STUDENT_ID)})).json()["enrollment"]
    as_student(user_id=STUDENT_ID)
    for item in ITEMS:
        await client.post(f"/api/v1/enrollments/{enrollment['enrollment_id']}/items/{item}/complete")
    return enrollment


async def test_items_alone_no_longer_complete_a_topic_that_has_a_test(
    client: AsyncClient, app, as_institution_head, as_student, seed_institution, seed_course, seed_entitlement, mock_seats
) -> None:
    enrollment = await _enrolled_with_tests(client, app, as_institution_head, as_student, seed_institution, seed_course, seed_entitlement)
    state = await _state(client, enrollment)
    topic = state["modules"][0]["topics"][0]
    assert topic["completed_items"] == topic["required_items"] == 2
    assert (topic["completed"], topic["test_required"], topic["test_passed"]) == (False, True, False)
    assert state["modules"][0]["completed"] is False and state["eligible_for_final"] is False
    events = await _events(app)
    assert events["topic.completed"] == events["module.completed"] == events["course.eligible_for_final"] == 0


async def test_passing_the_topic_then_module_test_completes_each_and_makes_the_student_eligible(
    client: AsyncClient, app, as_institution_head, as_student, seed_institution, seed_course, seed_entitlement, mock_seats
) -> None:
    enrollment = await _enrolled_with_tests(client, app, as_institution_head, as_student, seed_institution, seed_course, seed_entitlement)
    eid = enrollment["enrollment_id"]

    await _send(app, "attempt.finalized", _finalized(eid, TOPIC_TEST, "topic", "failed", attempt_id=1755000000006001), "e1")
    assert (await _events(app))["topic.completed"] == 0  # a failed attempt completes nothing

    await _send(app, "attempt.finalized", _finalized(eid, TOPIC_TEST, "topic", "passed", attempt_id=1755000000006002), "e2")
    events = await _events(app)
    assert events["topic.completed"] == 1 and events["module.completed"] == 0 and events["course.eligible_for_final"] == 0
    assert (await _state(client, enrollment))["modules"][0]["topics"][0]["test_passed"] is True

    await _send(app, "attempt.finalized", _finalized(eid, MODULE_TEST, "module", "passed", attempt_id=1755000000006003), "e3")
    events = await _events(app)
    assert events["module.completed"] == 1 and events["course.eligible_for_final"] == 1
    state = await _state(client, enrollment)
    assert state["modules"][0]["completed"] is True and state["eligible_for_final"] is True

    async with app.state.sessionmaker() as db:
        eligible = next(e.payload for e in (await db.execute(select(OutboxEvent))).scalars() if e.event_type == "course.eligible_for_final")
    assert eligible["student_user_id"] == str(STUDENT_ID)  # the payload notification-service relies on


async def test_redelivery_and_older_revisions_change_nothing_and_emit_nothing(
    client: AsyncClient, app, as_institution_head, as_student, seed_institution, seed_course, seed_entitlement, mock_seats
) -> None:
    enrollment = await _enrolled_with_tests(client, app, as_institution_head, as_student, seed_institution, seed_course, seed_entitlement)
    passed = _finalized(enrollment["enrollment_id"], TOPIC_TEST, "topic", "passed", revision=2)
    await _send(app, "attempt.finalized", passed, "e1")
    await _send(app, "attempt.finalized", passed, "e2")  # the same announcement again
    await _send(app, "attempt.finalized", {**passed, "result": "failed", "revision": 1}, "e3")  # an older one arriving late
    assert (await _events(app))["topic.completed"] == 1
    assert (await _state(client, enrollment))["modules"][0]["topics"][0]["test_passed"] is True


async def test_a_later_failing_attempt_keeps_the_pass_but_an_invalidation_of_it_takes_it_back(
    client: AsyncClient, app, as_institution_head, as_student, seed_institution, seed_course, seed_entitlement, mock_seats
) -> None:
    enrollment = await _enrolled_with_tests(client, app, as_institution_head, as_student, seed_institution, seed_course, seed_entitlement)
    eid, first, second = enrollment["enrollment_id"], 1755000000006010, 1755000000006011
    await _send(app, "attempt.finalized", _finalized(eid, TOPIC_TEST, "topic", "passed", attempt_id=first), "e1")
    await _send(app, "attempt.finalized", _finalized(eid, TOPIC_TEST, "topic", "failed", attempt_id=second), "e2")  # a retake that went badly
    assert (await _state(client, enrollment))["modules"][0]["topics"][0]["completed"] is True

    await _send(app, "attempt.finalized", {**_finalized(eid, TOPIC_TEST, "topic", "invalidated", attempt_id=first), "revision": 2}, "e3")
    topic = (await _state(client, enrollment))["modules"][0]["topics"][0]
    assert topic["completed"] is False and topic["test_passed"] is False  # an integrity case invalidated that pass


async def test_only_topic_and_module_tests_of_active_enrolments_count(
    client: AsyncClient, app, as_institution_head, as_student, seed_institution, seed_course, seed_entitlement, mock_seats
) -> None:
    enrollment = await _enrolled_with_tests(client, app, as_institution_head, as_student, seed_institution, seed_course, seed_entitlement)
    eid = enrollment["enrollment_id"]
    await _send(app, "attempt.finalized", _finalized(eid, TOPIC_TEST, "final", "passed"), "e1")  # a final test does not gate a topic
    await _send(app, "attempt.finalized", _finalized(eid, TOPIC_TEST, "practice", "passed"), "e2")
    await _send(app, "attempt.finalized", {**_finalized(eid, TOPIC_TEST, "topic", "passed"), "enrollment_id": None}, "e3")  # no enrolment
    await _send(app, "attempt.finalized", _finalized("1755000000009999", TOPIC_TEST, "topic", "passed"), "e4")  # an unknown one
    assert (await _events(app))["topic.completed"] == 0

    as_institution_head()
    await client.post(f"/api/v1/enrollments/{eid}/withdraw")
    await _send(app, "attempt.finalized", _finalized(eid, TOPIC_TEST, "topic", "passed"), "e5")  # withdrawn: nothing to complete
    assert (await _events(app))["topic.completed"] == 0
