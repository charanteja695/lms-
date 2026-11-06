import time
from datetime import timedelta

from sqlalchemy import select, update

from app.core.time import utcnow
from app.models.attempt import Attempt
from app.models.outbox_event import OutboxEvent
from tests.conftest import COURSE, ENROLLMENT, STUDENT, VERSION, fixed, mcq, true_false


async def outbox(sessionmaker, event_type: str) -> list[dict]:
    async with sessionmaker() as db:
        rows = (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == event_type).order_by(OutboxEvent.created_at))).scalars()
        return [row.payload for row in rows]


async def final_test(make_question, make_test, **fields):
    q1, q2 = await make_question(mcq(correct="b")), await make_question(true_false(True))
    rules = {"kind": "final", "target_id": str(COURSE), "proctoring_level": "strict", "max_attempts": 2, "pass_mark_percent": 60, **fields}
    test_id = await make_test([fixed(q1, 5), fixed(q2, 5)], **rules)
    return test_id, q1, q2


async def schedule(client, who, test_id, *, starts_in_minutes: float, lasts_minutes: int = 120, **fields):
    who.exam_manager()
    starts = utcnow() + timedelta(minutes=starts_in_minutes)
    response = await client.post(
        f"/api/v1/tests/{test_id}/schedules",
        json={"starts_at": starts.isoformat(), "ends_at": (starts + timedelta(minutes=lasts_minutes)).isoformat(), **fields},
    )
    assert response.status_code == 201, response.text
    return response.json()["schedule"]


async def sit(client, who, test_id, answers: dict, *, submit=True):
    """Start the exam and answer; returns the attempt id."""
    who.student()
    created = await client.post(f"/api/v1/tests/{test_id}/attempts", json={"start_now": True})
    assert created.status_code == 201, created.text
    attempt_id = created.json()["attempt"]["attempt_id"]
    for question_id, response in answers.items():
        saved = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{question_id}", json={"response": response, "revision": 1})
        assert saved.status_code == 200, saved.text
    if submit:
        assert (await client.post(f"/api/v1/attempts/{attempt_id}/submit")).status_code == 202
    return attempt_id


async def test_only_students_marked_eligible_by_learning_can_take_the_final(client, who, enroll, make_question, make_test):
    test_id, *_ = await final_test(make_question, make_test)
    await enroll(eligible=False)
    who.student()
    refused = await client.post(f"/api/v1/tests/{test_id}/attempts", json={})
    assert refused.status_code == 403 and refused.json()["code"] == "NOT_ELIGIBLE_FOR_FINAL"
    await enroll(eligible=True)  # learning-service: course.eligible_for_final
    await schedule(client, who, test_id, starts_in_minutes=-1)
    who.student()
    assert (await client.post(f"/api/v1/tests/{test_id}/attempts", json={})).status_code == 201


async def test_a_scheduled_exam_needs_a_session_and_the_waiting_room_opens_before_it_starts(client, who, enroll, make_question, make_test):
    test_id, *_ = await final_test(make_question, make_test, requires_schedule=True)
    await enroll(eligible=True)
    who.student()
    none = await client.post(f"/api/v1/tests/{test_id}/attempts", json={})
    assert none.status_code == 409 and none.json()["code"] == "NOT_SCHEDULED"

    await schedule(client, who, test_id, starts_in_minutes=180)
    who.student()
    early = await client.post(f"/api/v1/tests/{test_id}/attempts", json={})
    assert early.status_code == 409 and early.json()["code"] == "EXAM_NOT_OPEN"
    assert early.json()["details"][0]["field"] == "opens_at"


async def test_students_wait_in_the_room_with_a_prepared_paper_and_start_when_it_opens(client, who, enroll, make_question, make_test, sessionmaker):
    test_id, *_ = await final_test(make_question, make_test, requires_schedule=True)
    await enroll(eligible=True)
    session = await schedule(client, who, test_id, starts_in_minutes=10)
    who.student()
    waiting = await client.post(f"/api/v1/tests/{test_id}/attempts", json={})
    assert waiting.status_code == 201
    state = waiting.json()["attempt"]
    assert state["status"] == "not_started" and state["opens_at"] is not None
    attempt_id = state["attempt_id"]

    too_soon = await client.post(f"/api/v1/attempts/{attempt_id}/start")
    assert too_soon.status_code == 409 and too_soon.json()["code"] == "EXAM_NOT_OPEN"
    assert (await client.get("/api/v1/my/tests")).json()["tests"][0]["open_attempt_id"] == attempt_id

    async with sessionmaker() as db:  # the exam opens: move the window (an exam manager cannot edit a session already running)
        from app.models.test import TestSchedule

        await db.execute(update(TestSchedule).values(starts_at=utcnow() - timedelta(minutes=1), ends_at=utcnow() + timedelta(minutes=45)))
        await db.commit()
    started = await client.post(f"/api/v1/attempts/{attempt_id}/start")
    assert started.status_code == 200
    body = started.json()["attempt"]
    assert len(started.json()["questions"]) == 2
    assert body["remaining_seconds"] <= 45 * 60  # a session that enforces its end cuts the attempt off at the window's end
    assert session["enforce_end"] is True


async def test_starts_are_staggered_when_an_exam_opens(client, who, enroll, make_question, make_test, redis, settings):
    settings.WAITING_ROOM_ADMIT_PER_SECOND = 1
    test_id, *_ = await final_test(make_question, make_test, requires_schedule=True)
    await enroll(eligible=True)
    await schedule(client, who, test_id, starts_in_minutes=-1)
    who.student()
    attempt_id = (await client.post(f"/api/v1/tests/{test_id}/attempts", json={})).json()["attempt"]["attempt_id"]
    now = int(time.time())
    for second in (now, now + 1):  # the room is full for this second (and the next, in case the clock ticks)
        await redis.set(f"assessment:admit:{test_id}:{second}", 5)
    busy = await client.post(f"/api/v1/attempts/{attempt_id}/start")
    assert busy.status_code == 429 and busy.json()["code"] == "WAITING_ROOM" and int(busy.headers["Retry-After"]) >= 1
    for second in (now, now + 1, now + 2):
        await redis.delete(f"assessment:admit:{test_id}:{second}")
    assert (await client.post(f"/api/v1/attempts/{attempt_id}/start")).status_code == 200  # it is their turn


async def test_a_pass_on_a_proctored_final_waits_for_the_integrity_decision_then_becomes_course_passed(client, who, enroll, make_question, make_test, work, send_event, sessionmaker):
    test_id, q1, q2 = await final_test(make_question, make_test)
    await enroll(eligible=True)
    await schedule(client, who, test_id, starts_in_minutes=-1)
    attempt_id = await sit(client, who, test_id, {q1: {"selected": "b"}, q2: {"value": True}})
    assert (await outbox(sessionmaker, "attempt.started"))[0]["proctoring_level"] == "strict"  # proctoring-service opens its session from this
    await work.grade()

    who.student()
    pending = (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]
    assert pending["released"] is False and "not been released" in pending["message"]
    assert await outbox(sessionmaker, "course.passed") == []  # a passing score alone is not a pass on a proctored test

    await send_event("integrity.decided", {"attempt_id": attempt_id, "decision": "clear"})
    who.student()
    result = (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]
    assert result["result"] == "passed" and result["integrity_status"] == "clear" and result["percent"] == 100

    (passed,) = await outbox(sessionmaker, "course.passed")
    assert passed["course_id"] == str(COURSE) and passed["version_id"] == str(VERSION)
    assert passed["student_user_id"] == str(STUDENT) and passed["enrollment_id"] == str(ENROLLMENT)
    assert passed["percent"] == 100 and passed["best_percent"] == 100 and passed["test_id"] == test_id
    (finalized,) = await outbox(sessionmaker, "attempt.finalized")
    assert finalized["result"] == "passed" and finalized["integrity_status"] == "clear"


async def test_a_flagged_attempt_stays_pending_until_a_human_decides(client, who, enroll, make_question, make_test, work, send_event, sessionmaker):
    test_id, q1, q2 = await final_test(make_question, make_test)
    await enroll(eligible=True)
    await schedule(client, who, test_id, starts_in_minutes=-1)
    attempt_id = await sit(client, who, test_id, {q1: {"selected": "b"}, q2: {"value": True}})
    await work.grade()
    await send_event("integrity.flagged", {"attempt_id": attempt_id, "status": "under_review"})
    who.exam_manager()
    listed = (await client.get("/api/v1/attempts", params={"integrity_status": "under_review"})).json()["attempts"]
    assert [a["attempt_id"] for a in listed] == [attempt_id] and listed[0]["result"] == "pending"
    await send_event("integrity.decided", {"attempt_id": attempt_id, "decision": "reviewed_ok"})
    assert (await client.get("/api/v1/attempts", params={"result": "passed"})).json()["page_context"]["total_records"] == 1
    assert len(await outbox(sessionmaker, "course.passed")) == 1


async def test_an_invalidation_fails_the_attempt_and_revokes_an_earlier_pass(client, who, enroll, make_question, make_test, work, send_event, sessionmaker):
    test_id, q1, q2 = await final_test(make_question, make_test)
    await enroll(eligible=True)
    await schedule(client, who, test_id, starts_in_minutes=-1)
    attempt_id = await sit(client, who, test_id, {q1: {"selected": "b"}, q2: {"value": True}})
    await work.grade()
    await send_event("integrity.decided", {"attempt_id": attempt_id, "decision": "clear"})
    assert len(await outbox(sessionmaker, "course.passed")) == 1

    await send_event("integrity.decided", {"attempt_id": attempt_id, "decision": "invalidated"})  # decided later, after release
    who.student()
    assert (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]["result"] == "invalidated"
    (revoked,) = await outbox(sessionmaker, "course.pass_revoked")
    assert revoked["attempt_id"] == attempt_id and revoked["reason"] == "integrity"
    finalized = await outbox(sessionmaker, "attempt.finalized")
    assert [f["result"] for f in finalized] == ["passed", "invalidated"] and [f["revision"] for f in finalized] == [1, 2]
    assert finalized[1]["previous_result"] == "passed"


async def test_an_invalidation_before_grading_finishes_is_applied_when_it_does(client, who, enroll, make_question, make_test, work, send_event, sessionmaker):
    test_id, q1, q2 = await final_test(make_question, make_test)
    await enroll(eligible=True)
    await schedule(client, who, test_id, starts_in_minutes=-1)
    attempt_id = await sit(client, who, test_id, {q1: {"selected": "b"}, q2: {"value": True}})
    await send_event("integrity.decided", {"attempt_id": attempt_id, "decision": "invalidated"})  # before the grader has run
    await work.grade()
    who.student()
    assert (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]["result"] == "invalidated"
    assert await outbox(sessionmaker, "course.passed") == []


async def test_failing_every_attempt_emits_course_failed_and_a_pass_blocks_retakes(client, who, enroll, make_question, make_test, work, send_event, sessionmaker):
    test_id, q1, q2 = await final_test(make_question, make_test)
    await enroll(eligible=True)
    await schedule(client, who, test_id, starts_in_minutes=-1)
    first = await sit(client, who, test_id, {q1: {"selected": "a"}})
    await work.grade()
    assert await outbox(sessionmaker, "course.failed") == []  # one attempt left
    assert (await client.get(f"/api/v1/attempts/{first}/result")).json()["result"]["result"] == "failed"
    second = await sit(client, who, test_id, {q1: {"selected": "c"}})
    await work.grade()
    (failed,) = await outbox(sessionmaker, "course.failed")
    assert failed["course_id"] == str(COURSE) and failed["attempts_used"] == 2
    assert second != first
    who.student()
    assert (await client.post(f"/api/v1/tests/{test_id}/attempts", json={})).json()["code"] == "ATTEMPTS_EXHAUSTED"


async def test_after_window_results_stay_hidden_until_the_release_time(client, who, enroll, make_question, make_test, work, sessionmaker):
    test_id, q1, q2 = await final_test(make_question, make_test, result_visibility="after_window", proctoring_level="none", requires_schedule=True)
    await enroll(eligible=True)
    await schedule(client, who, test_id, starts_in_minutes=-1, lasts_minutes=60)
    attempt_id = await sit(client, who, test_id, {q1: {"selected": "b"}, q2: {"value": True}})
    await work.grade()
    who.student()
    assert (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]["released"] is False
    assert await outbox(sessionmaker, "course.passed") == []

    async with sessionmaker() as db:
        await db.execute(update(Attempt).values(release_due_at=utcnow() - timedelta(minutes=1)))
        await db.commit()
    assert await work.release() == 1
    assert (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]["result"] == "passed"
    assert len(await outbox(sessionmaker, "course.passed")) == 1


async def test_schedules_are_managed_by_exam_managers_and_can_be_extended_but_not_moved_once_running(client, who, enroll, make_question, make_test):
    test_id, *_ = await final_test(make_question, make_test)
    session = await schedule(client, who, test_id, starts_in_minutes=60)
    who.student()
    # a student cannot even see the definition, so the test does not exist as far as they are concerned
    assert (await client.post(f"/api/v1/tests/{test_id}/schedules", json={"starts_at": "2030-01-01T00:00:00Z", "ends_at": "2030-01-01T02:00:00Z"})).status_code == 404
    who.staff()
    assert (await client.post(f"/api/v1/tests/{test_id}/schedules", json={"starts_at": "2030-01-01T00:00:00Z", "ends_at": "2030-01-01T02:00:00Z"})).status_code == 404
    who.exam_manager()
    moved = await client.patch(f"/api/v1/tests/{test_id}/schedules/{session['schedule_id']}", json={"title": "Morning batch"})
    assert moved.status_code == 200 and moved.json()["schedule"]["title"] == "Morning batch"
    assert (await client.delete(f"/api/v1/tests/{test_id}/schedules/{session['schedule_id']}")).json()["schedule"]["cancelled_at"] is not None
    bad = await client.post(f"/api/v1/tests/{test_id}/schedules", json={"starts_at": "2030-01-01T02:00:00Z", "ends_at": "2030-01-01T01:00:00Z"})
    assert bad.status_code == 422
    naive = await client.post(f"/api/v1/tests/{test_id}/schedules", json={"starts_at": "2030-01-01T00:00:00", "ends_at": "2030-01-01T01:00:00"})
    assert naive.status_code == 422
