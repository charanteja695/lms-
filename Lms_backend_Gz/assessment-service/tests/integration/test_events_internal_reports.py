from datetime import timedelta

from sqlalchemy import select, update

from app.core.time import utcnow
from app.models.outbox_event import OutboxEvent
from app.models.refs import EnrollmentRef, VersionRef, VersionTarget
from app.models.test import TestAssignment
from tests.conftest import (
    COURSE,
    EMPLOYER,
    ENROLLMENT,
    INTERNAL_TOKEN,
    MODULE,
    STUDENT,
    TOPIC,
    VERSION,
    fixed,
    mcq,
    true_false,
)

INTERNAL = {"X-Internal-Service-Token": INTERNAL_TOKEN}


async def outbox(sessionmaker, event_type: str) -> list[dict]:
    async with sessionmaker() as db:
        rows = (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == event_type).order_by(OutboxEvent.created_at))).scalars()
        return [row.payload for row in rows]


# ----------------------------------------------------------------------------- read-models from events


async def test_course_published_builds_the_structure_and_republishing_replaces_it(enroll, send_event, sessionmaker):
    await enroll(topic_test_id=1755000000000777)
    async with sessionmaker() as db:
        targets = {(t.target_type, t.target_id) for t in (await db.execute(select(VersionTarget))).scalars()}
        assert targets == {("course", COURSE), ("module", MODULE), ("topic", TOPIC), ("test", 1755000000000777)}
        assert (await db.get(VersionRef, VERSION)).course_id == COURSE
    await send_event("course.published", {"course_id": str(COURSE), "version_id": str(VERSION), "modules": [{"module_id": str(MODULE), "topics": []}]})
    async with sessionmaker() as db:
        targets = {(t.target_type, t.target_id) for t in (await db.execute(select(VersionTarget))).scalars()}
        assert targets == {("course", COURSE), ("module", MODULE)}


async def test_removing_an_enrolment_closes_the_tests_and_events_are_processed_once(client, who, enroll, send_event, make_question, make_test, sessionmaker):
    q1 = await make_question(mcq())
    test_id = await make_test([fixed(q1)], kind="module", target_id=str(MODULE))
    await enroll()
    who.student()
    assert (await client.post(f"/api/v1/tests/{test_id}/attempts", json={})).status_code == 201
    async with sessionmaker() as db:
        await db.execute(update(EnrollmentRef).values(active=True))
    removed = {"enrollment_id": str(ENROLLMENT), "student_user_id": str(STUDENT), "version_id": str(VERSION)}
    await send_event("enrollment.removed", removed, event_id="evt-1")
    async with sessionmaker() as db:
        assert (await db.get(EnrollmentRef, ENROLLMENT)).active is False
        await db.execute(update(EnrollmentRef).values(active=True))
        await db.commit()
    await send_event("enrollment.removed", removed, event_id="evt-1")  # a redelivery changes nothing
    async with sessionmaker() as db:
        assert (await db.get(EnrollmentRef, ENROLLMENT)).active is True


async def test_a_retired_version_keeps_serving_students_already_enrolled(client, who, enroll, send_event, make_question, make_test):
    q1 = await make_question(mcq())
    test_id = await make_test([fixed(q1)], kind="module", target_id=str(MODULE))
    await enroll()
    await send_event("course.retired", {"course_id": str(COURSE), "version_id": str(VERSION)})
    who.student()
    assert (await client.post(f"/api/v1/tests/{test_id}/attempts", json={})).status_code == 201


async def test_unknown_events_are_ignored(send_event):
    await send_event("something.else", {"anything": 1})
    await send_event("integrity.decided", {"attempt_id": "1755000000001111", "decision": "clear"})  # an attempt we do not know


# ----------------------------------------------------------------------------- internal API


async def hiring_test(client, who, make_test_payload=None):
    """An employer's own hiring assessment, authored and approved by its people."""
    who.recruiter()
    question = (await client.post("/api/v1/questions", json=mcq(default_marks=4))).json()["question"]["question_id"]
    await client.post(f"/api/v1/questions/{question}/submit")
    who.employer_admin()
    await client.post(f"/api/v1/questions/{question}/approve", json={})
    who.recruiter()
    test_id = (
        await client.post(
            "/api/v1/tests",
            json={"title": "Backend screen", "kind": "hiring", "duration_minutes": 20, "pass_mark_percent": 50, "sections": [{"title": "A", "slots": [fixed(question)]}]},
        )
    ).json()["test"]["test_id"]
    await client.post(f"/api/v1/tests/{test_id}/submit")
    who.employer_admin()
    await client.post(f"/api/v1/tests/{test_id}/approve", json={})
    return test_id, question


async def test_internal_endpoints_need_the_service_token(client):
    assert (await client.post("/api/v1/internal/assignments", json={})).status_code == 403
    bad = await client.get("/api/v1/internal/queue", headers={"X-Internal-Service-Token": "wrong"})
    assert bad.status_code == 403 and bad.json()["code"] == "INTERNAL_CALLER_REQUIRED"
    ok = await client.get("/api/v1/internal/queue", headers=INTERNAL)
    assert ok.status_code == 200 and ok.json()["queue"]["grading"] == {"submitted": 0, "stuck": 0}


async def test_a_hiring_assessment_is_only_open_to_invited_candidates(client, who, work):
    test_id, question = await hiring_test(client, who)
    who.student()
    assert (await client.post(f"/api/v1/tests/{test_id}/attempts", json={})).json()["code"] == "NOT_INVITED"
    assert (await client.get("/api/v1/my/tests")).json()["tests"] == []

    invited = await client.post(
        "/api/v1/internal/assignments",
        json={"test_id": test_id, "user_id": str(STUDENT), "reference": "application:7", "max_attempts": 1},
        headers=INTERNAL,
    )
    assert invited.status_code == 201 and invited.json()["assignment"]["reference"] == "application:7"
    who.student()
    listed = (await client.get("/api/v1/my/tests")).json()["tests"]
    assert [t["test_id"] for t in listed] == [test_id] and listed[0]["attempts_left"] == 1

    attempt_id = (await client.post(f"/api/v1/tests/{test_id}/attempts", json={"start_now": True})).json()["attempt"]["attempt_id"]
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{question}", json={"response": {"selected": "b"}, "revision": 1})
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    await work.everything()

    assert (await client.post(f"/api/v1/tests/{test_id}/attempts", json={})).json()["code"] == "ATTEMPTS_EXHAUSTED"  # the invitation allowed one
    who.employer_admin()  # the employer sees the candidate's result
    results = (await client.get(f"/api/v1/tests/{test_id}/results")).json()["attempts"]
    assert [(r["attempt_id"], r["result"], r["percent"]) for r in results] == [(attempt_id, "passed", 100)]
    assert (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]["questions"][0]["answer_key"] == {"correct": "b"}
    who.staff()  # the candidate's institution staff do not see an employer's assessment
    assert (await client.get(f"/api/v1/attempts/{attempt_id}/result")).status_code == 404
    assert (await client.get("/api/v1/attempts")).json()["attempts"] == []
    who.employer_admin(user_id=1755000000007150, organization_id=1755000000007006)  # another employer
    assert (await client.get(f"/api/v1/attempts/{attempt_id}/result")).status_code == 404


async def test_invitation_windows(client, who, sessionmaker):
    test_id, _ = await hiring_test(client, who)
    opens = (utcnow() + timedelta(days=1)).isoformat()
    await client.post("/api/v1/internal/assignments", json={"test_id": test_id, "user_id": str(STUDENT), "opens_at": opens}, headers=INTERNAL)
    who.student()
    early = await client.post(f"/api/v1/tests/{test_id}/attempts", json={})
    assert early.status_code == 409 and early.json()["code"] == "NOT_YET_OPEN"
    async with sessionmaker() as db:
        await db.execute(update(TestAssignment).values(opens_at=None, expires_at=utcnow() - timedelta(hours=1)))
        await db.commit()
    assert (await client.post(f"/api/v1/tests/{test_id}/attempts", json={})).json()["code"] == "INVITATION_EXPIRED"


async def test_only_hiring_tests_can_be_assigned(client, who, make_question, make_test):
    q1 = await make_question(mcq())
    module = await make_test([fixed(q1)], kind="module", target_id=str(MODULE))
    refused = await client.post("/api/v1/internal/assignments", json={"test_id": module, "user_id": str(STUDENT)}, headers=INTERNAL)
    assert refused.status_code == 404


async def test_proctoring_service_pauses_terminates_and_decides_through_the_internal_api(client, who, enroll, make_question, make_test, work):
    q1 = await make_question(mcq(correct="b"))
    test_id = await make_test([fixed(q1, 10)], kind="module", target_id=str(MODULE), proctoring_level="basic")
    await enroll()
    who.student()
    attempt_id = (await client.post(f"/api/v1/tests/{test_id}/attempts", json={"start_now": True})).json()["attempt"]["attempt_id"]
    paused = await client.post(f"/api/v1/internal/attempts/{attempt_id}/pause", json={"reason": "no face"}, headers=INTERNAL)
    assert paused.json()["attempt"]["status"] == "paused"
    assert (await client.post(f"/api/v1/internal/attempts/{attempt_id}/unpause", headers=INTERNAL)).json()["attempt"]["status"] == "in_progress"
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "b"}, "revision": 1})
    terminated = await client.post(f"/api/v1/internal/attempts/{attempt_id}/terminate", json={"reason": "second person"}, headers=INTERNAL)
    assert terminated.json()["attempt"]["submit_reason"] == "terminated"
    await work.everything()
    decided = await client.post(f"/api/v1/internal/attempts/{attempt_id}/integrity", json={"decision": "invalidated"}, headers=INTERNAL)
    assert decided.status_code == 200
    who.student()
    assert (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]["result"] == "invalidated"
    assert (await client.post("/api/v1/internal/attempts/1755000000001111/integrity", json={"decision": "clear"}, headers=INTERNAL)).status_code == 404
    assert (await client.post(f"/api/v1/internal/attempts/{attempt_id}/integrity", json={"decision": "maybe"}, headers=INTERNAL)).status_code == 422


# ----------------------------------------------------------------------------- reports


async def two_attempts(client, who, enroll, make_question, make_test, work):
    q1, q2 = await make_question(mcq(correct="b")), await make_question(true_false(True))
    test_id = await make_test([fixed(q1, 5), fixed(q2, 5)], kind="module", target_id=str(MODULE))
    await enroll()
    await enroll(1755000000007102, enrollment_id=1755000000008006)
    await enroll(1755000000007107, enrollment_id=1755000000008007, organization_id=1755000000007004)
    attempts = []
    for student, org, answers in (
        (STUDENT, 1755000000007003, {q1: {"selected": "b"}, q2: {"value": True}}),
        (1755000000007102, 1755000000007003, {q1: {"selected": "a"}, q2: {"value": True}}),
        (1755000000007107, 1755000000007004, {q1: {"selected": "b"}}),
    ):
        who.student(student, org)
        attempt_id = (await client.post(f"/api/v1/tests/{test_id}/attempts", json={"start_now": True})).json()["attempt"]["attempt_id"]
        for question_id, response in answers.items():
            await client.put(f"/api/v1/attempts/{attempt_id}/answers/{question_id}", json={"response": response, "revision": 1})
        await client.post(f"/api/v1/attempts/{attempt_id}/submit")
        attempts.append(attempt_id)
    await work.everything()
    return test_id, (q1, q2), attempts


async def test_who_sees_which_attempts(client, who, enroll, make_question, make_test, work):
    test_id, _, (a1, a2, a3) = await two_attempts(client, who, enroll, make_question, make_test, work)
    ids = lambda response: sorted(a["attempt_id"] for a in response.json()["attempts"])  # noqa: E731

    who.student()
    assert ids(await client.get("/api/v1/attempts")) == [a1]  # a student sees only their own
    who.exam_manager()
    assert ids(await client.get("/api/v1/attempts")) == sorted([a1, a2, a3])
    assert ids(await client.get(f"/api/v1/tests/{test_id}/results", params={"result": "passed"})) == sorted([a1])
    who.staff()  # institution A's staff
    assert ids(await client.get("/api/v1/attempts")) == sorted([a1, a2])
    assert (await client.get(f"/api/v1/attempts/{a3}/result")).status_code == 404
    assert (await client.get(f"/api/v1/attempts/{a1}/result")).json()["result"]["questions"][0]["answer_key"]  # staff review with keys
    who.staff(user_id=1755000000007109, organization_id=1755000000007004)
    assert ids(await client.get("/api/v1/attempts")) == [a3]
    who.recruiter()  # an employer has no business with a platform test
    assert ids(await client.get("/api/v1/attempts")) == []


async def test_analytics_and_csv_export(client, who, enroll, make_question, make_test, work):
    test_id, _, (a1, a2, a3) = await two_attempts(client, who, enroll, make_question, make_test, work)
    who.exam_manager()
    stats = (await client.get(f"/api/v1/tests/{test_id}/analytics")).json()["analytics"]
    assert stats["attempts"] == {"graded": 3} and stats["graded"] == 3
    assert stats["average_percent"] == 66.67 and stats["pass_rate_percent"] == 33.33  # 100%, 50%, 50% against a 60% pass mark
    assert sum(b["count"] for b in stats["distribution"]) == 3
    assert len(stats["questions"]) == 2 and stats["questions"][0]["times_served"] == 3

    export = await client.get(f"/api/v1/tests/{test_id}/results/export")
    assert export.status_code == 200 and export.headers["content-type"].startswith("text/csv")
    lines = export.text.strip().splitlines()
    assert lines[0].startswith("attempt_id,user_id,organization_id") and len(lines) == 4
    assert any(line.startswith(a1) and ",passed," in line for line in lines[1:])
    who.staff()
    assert (await client.get(f"/api/v1/tests/{test_id}/analytics")).status_code == 403
    assert (await client.get(f"/api/v1/tests/{test_id}/results/export")).status_code == 403


async def test_question_statistics_are_recomputed_after_attempts(client, who, enroll, make_question, make_test, work, redis, sessionmaker, settings):
    from app.worker.runner import process_dirty

    test_id, (q1, q2), _ = await two_attempts(client, who, enroll, make_question, make_test, work)
    assert await process_dirty(sessionmaker, redis, settings) == 1  # the test was marked dirty when results were released
    who.author()
    question = (await client.get(f"/api/v1/questions/{q1}")).json()["question"]
    assert question["stats"]["sample_size"] == 3
    assert question["stats"]["difficulty_index"] == 0.6667  # two of three got it right
    assert question["stats"]["discrimination"] is None  # too few attempts for a meaningful discrimination index
    forced = await client.post(f"/api/v1/questions/{q2}/stats/recompute")
    assert forced.json()["stats"]["sample_size"] == 3  # an unanswered question counts, as zero


async def test_practice_tests_are_open_to_any_student(client, who, make_question, make_test):
    q1 = await make_question(mcq())
    test_id = await make_test([fixed(q1)], kind="practice", title="Warm-up quiz")
    who.student()
    tests = (await client.get("/api/v1/my/tests")).json()["tests"]
    assert [t["test_id"] for t in tests] == [test_id]
    detail = (await client.get(f"/api/v1/my/tests/{test_id}")).json()
    assert detail["test"]["title"] == "Warm-up quiz" and detail["sections"][0]["title"] == "Section 1"
    assert "questions" not in detail and "answer_key" not in str(detail)
    who.staff()
    assert (await client.get("/api/v1/my/tests")).status_code == 403
    assert EMPLOYER  # (imported for the hiring helper)
