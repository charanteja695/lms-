from sqlalchemy import select

from app.models.attempt import Attempt, AttemptAnswer, AttemptEvent
from app.models.outbox_event import OutboxEvent
from tests.conftest import MODULE, TOPIC, fixed, mcq, pool, true_false

TOPIC_TEST_TARGET = str(TOPIC)


async def outbox(sessionmaker, event_type: str) -> list[dict]:
    async with sessionmaker() as db:
        rows = (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == event_type).order_by(OutboxEvent.created_at))).scalars()
        return [row.payload for row in rows]


async def module_test(make_question, make_test, *, marks=(2, 3), **fields):
    q1, q2 = await make_question(mcq(correct="b")), await make_question(true_false(True))
    test_id = await make_test([fixed(q1, marks[0]), fixed(q2, marks[1])], kind="module", target_id=str(MODULE), **fields)
    return test_id, q1, q2


async def start(client, who, test_id, student=None):
    who.student(*([student] if student else []))
    created = await client.post(f"/api/v1/tests/{test_id}/attempts", json={"start_now": True})
    assert created.status_code == 201, created.text
    return created.json()["attempt"]["attempt_id"]


async def paper(client, attempt_id):
    response = await client.post(f"/api/v1/attempts/{attempt_id}/resume")
    assert response.status_code == 200, response.text
    return response.json()


async def test_a_student_takes_a_module_test_from_enrolment_to_result(client, who, enroll, make_question, make_test, work, sessionmaker):
    test_id, q1, q2 = await module_test(make_question, make_test)
    await enroll()
    who.student()

    mine = (await client.get("/api/v1/my/tests")).json()["tests"]
    assert [t["test_id"] for t in mine] == [test_id] and mine[0]["can_start"] is True and mine[0]["attempts_left"] == 3

    prepared = await client.post(f"/api/v1/tests/{test_id}/attempts", json={})
    assert prepared.status_code == 201
    state = prepared.json()["attempt"]
    assert state["status"] == "not_started" and state["deadline_at"] is None
    attempt_id = state["attempt_id"]
    assert (await client.get(f"/api/v1/attempts/{attempt_id}")).json()["questions"] == []  # nothing to read before the start

    started = await client.post(f"/api/v1/attempts/{attempt_id}/start")
    assert started.status_code == 200
    body = started.json()
    assert body["attempt"]["status"] == "in_progress" and 0 < body["attempt"]["remaining_seconds"] <= 1800
    assert len(body["questions"]) == 2
    for question in body["questions"]:
        assert "answer_key" not in question and "answer_key" not in str(question["body"])  # the key never reaches the student

    right = {q["question_id"]: q for q in body["questions"]}
    assert (await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "b"}, "revision": 1})).status_code == 200
    assert (await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q2}", json={"response": {"value": False}, "revision": 1})).status_code == 200
    assert set(right) == {q1, q2}

    submitted = await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    assert submitted.status_code == 202 and submitted.json()["attempt"]["status"] == "submitted"
    assert (await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "a"}, "revision": 2})).status_code == 409

    await work.grade()
    result = (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]
    assert result["status"] == "graded" and result["released"] is True
    assert (result["score"], result["max_score"], result["percent"]) == (2, 5, 40)
    assert result["result"] == "failed" and result["pass_mark_percent"] == 60
    assert result["questions"] is None  # review policy `none`: the score only

    finalized = await outbox(sessionmaker, "attempt.finalized")
    assert finalized[0]["result"] == "failed" and finalized[0]["target_type"] == "module" and finalized[0]["revision"] == 1
    # learning-service completes topics/modules from exactly these keys (its assessment_events.handle_attempt_finalized)
    assert {"enrollment_id", "test_id", "test_kind", "result", "percent", "attempt_id", "revision"} <= finalized[0].keys()
    assert finalized[0]["test_kind"] == "module" and finalized[0]["enrollment_id"] and finalized[0]["test_id"] == test_id
    assert (await outbox(sessionmaker, "attempt.started"))[0]["deadline_at"]
    assert (await outbox(sessionmaker, "attempt.submitted"))[0]["submit_reason"] == "manual"
    assert (await outbox(sessionmaker, "attempt.graded"))[0]["percent"] == 40


async def test_answers_are_buffered_in_redis_then_flushed_to_the_database(client, who, enroll, make_question, make_test, work, sessionmaker, redis):
    test_id, q1, q2 = await module_test(make_question, make_test)
    await enroll()
    attempt_id = await start(client, who, test_id)
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "b"}, "revision": 1})

    async with sessionmaker() as db:
        assert (await db.execute(select(AttemptAnswer))).scalars().all() == []  # nothing in the database yet
    assert await redis.hlen(f"assessment:answers:{attempt_id}") == 1
    reloaded = (await paper(client, attempt_id))["questions"]  # a resume still shows it: reads overlay the buffer
    assert next(q for q in reloaded if q["question_id"] == q1)["answer"]["response"] == {"selected": "b"}

    assert await work.flush() == 1
    async with sessionmaker() as db:
        row = (await db.execute(select(AttemptAnswer))).scalar_one()
        assert row.response == {"selected": "b"} and row.revision == 1
    assert await work.flush() == 0  # nothing dirty any more


async def test_a_stale_revision_never_overwrites_a_newer_answer(client, who, enroll, make_question, make_test, work):
    test_id, q1, _ = await module_test(make_question, make_test)
    await enroll()
    attempt_id = await start(client, who, test_id)
    url = f"/api/v1/attempts/{attempt_id}/answers/{q1}"
    assert (await client.put(url, json={"response": {"selected": "c"}, "revision": 5})).json()["answers"][0]["status"] == "saved"
    stale = await client.put(url, json={"response": {"selected": "a"}, "revision": 3})
    assert stale.json()["answers"][0]["status"] == "stale"
    await work.flush()
    answers = {q["question_id"]: q["answer"] for q in (await paper(client, attempt_id))["questions"]}
    assert answers[q1]["response"] == {"selected": "c"} and answers[q1]["revision"] == 5


async def test_a_cleared_answer_is_saved_as_no_answer(client, who, enroll, make_question, make_test, work):
    test_id, q1, _ = await module_test(make_question, make_test)
    await enroll()
    attempt_id = await start(client, who, test_id)
    url = f"/api/v1/attempts/{attempt_id}/answers/{q1}"
    await client.put(url, json={"response": {"selected": "b"}, "revision": 1})
    await client.put(url, json={"response": None, "revision": 2})
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    await work.grade()
    assert (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]["score"] == 0


async def test_an_invalid_answer_is_rejected_and_the_batch_reports_each_answer(client, who, enroll, make_question, make_test):
    test_id, q1, q2 = await module_test(make_question, make_test)
    await enroll()
    attempt_id = await start(client, who, test_id)
    rejected = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "zzz"}})
    assert rejected.status_code == 422 and rejected.json()["details"][0]["code"] == "INVALID_ANSWER"
    batch = await client.put(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"answers": [{"question_id": q1, "response": {"selected": "zzz"}}, {"question_id": q2, "response": {"value": True}, "revision": 1}, {"question_id": "1755000000001234", "response": {"value": True}}]},
    )
    statuses = [(a["status"], (a["error"] or {}).get("code")) for a in batch.json()["answers"]]
    assert statuses == [("rejected", "INVALID_ANSWER"), ("saved", None), ("rejected", "QUESTION_NOT_IN_ATTEMPT")]


async def test_a_passing_attempt_finalises_as_passed(client, who, enroll, make_question, make_test, work):
    test_id, q1, q2 = await module_test(make_question, make_test)
    await enroll()
    attempt_id = await start(client, who, test_id)
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "b"}, "revision": 1})
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q2}", json={"response": {"value": True}, "revision": 1})
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    await work.grade()
    result = (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]
    assert (result["score"], result["percent"], result["result"]) == (5, 100, "passed")


async def test_negative_marking_costs_a_wrong_answer_but_never_takes_the_score_below_zero(client, who, enroll, make_question, make_test, work):
    test_id, q1, q2 = await module_test(make_question, make_test, negative_marking_percent=50)
    await enroll()
    attempt_id = await start(client, who, test_id)
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "a"}, "revision": 1})  # wrong: -1
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q2}", json={"response": {"value": False}, "revision": 1})  # wrong: -1.5
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    await work.grade()
    result = (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]
    assert result["score"] == 0 and result["percent"] == 0


async def test_review_policy_shows_answers_and_explanations_only_once_released(client, who, enroll, make_question, make_test, work):
    q1 = await make_question(mcq(correct="b", explanation="Because B is second."))
    test_id = await make_test([fixed(q1, 1)], kind="module", target_id=str(MODULE), review_policy="answers", result_visibility="manual")
    await enroll()
    attempt_id = await start(client, who, test_id)
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "a"}, "revision": 1})
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    await work.grade()

    held = (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]
    assert held["released"] is False and held["score"] is None and "not been released" in held["message"]

    who.exam_manager()
    assert (await client.post(f"/api/v1/tests/{test_id}/release-results")).json()["scheduled"] == 1
    await work.release()
    who.student()
    released = (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]
    assert released["released"] is True and released["result"] == "failed"
    review = released["questions"][0]
    assert review["answer_key"] == {"correct": "b"} and review["explanation"] == "Because B is second."
    assert review["response"] == {"selected": "a"} and review["is_correct"] is False


async def test_not_enrolled_students_and_other_tests_targets_are_refused(client, who, enroll, make_question, make_test):
    test_id, *_ = await module_test(make_question, make_test)
    who.student()
    refused = await client.post(f"/api/v1/tests/{test_id}/attempts", json={})
    assert refused.status_code == 403 and refused.json()["code"] == "NOT_ENROLLED"
    assert (await client.get("/api/v1/my/tests")).json()["tests"] == []
    await enroll(organization_id=1755000000007003, module_id=1755000000008099, topic_id=1755000000008098)  # enrolled in a version without this module
    assert (await client.post(f"/api/v1/tests/{test_id}/attempts", json={})).status_code == 403


async def test_a_cloned_course_version_still_reaches_the_same_test(client, who, enroll, make_question, make_test):
    test_id, *_ = await module_test(make_question, make_test)
    await enroll(version_id=1755000000008102, module_id=1755000000008103, topic_id=1755000000008104, module_test_id=int(test_id))
    who.student()
    assert (await client.post(f"/api/v1/tests/{test_id}/attempts", json={})).status_code == 201


async def test_attempt_limits_and_cooldown(client, who, enroll, make_question, make_test, work):
    test_id, q1, _ = await module_test(make_question, make_test, max_attempts=2, cooldown_hours=24)
    await enroll()
    first = await start(client, who, test_id)
    await client.post(f"/api/v1/attempts/{first}/submit")
    await work.grade()
    who.student()
    cooling = await client.post(f"/api/v1/tests/{test_id}/attempts", json={})
    assert cooling.status_code == 409 and cooling.json()["code"] == "COOLDOWN"
    assert cooling.json()["details"][0]["field"] == "next_available_at"
    listed = (await client.get("/api/v1/my/tests")).json()["tests"][0]
    assert listed["can_start"] is False and listed["reason"] == "COOLDOWN" and listed["attempts_left"] == 1


async def test_attempts_run_out(client, who, enroll, make_question, make_test, work):
    test_id, *_ = await module_test(make_question, make_test, max_attempts=1)
    await enroll()
    attempt_id = await start(client, who, test_id)
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    who.student()
    refused = await client.post(f"/api/v1/tests/{test_id}/attempts", json={})
    assert refused.status_code == 409 and refused.json()["code"] == "ATTEMPTS_EXHAUSTED"


async def test_creating_an_attempt_twice_returns_the_same_open_attempt(client, who, enroll, make_question, make_test):
    test_id, *_ = await module_test(make_question, make_test)
    await enroll()
    who.student()
    first = (await client.post(f"/api/v1/tests/{test_id}/attempts", json={}, headers={"Idempotency-Key": "attempt-0001-x"})).json()["attempt"]["attempt_id"]
    second = (await client.post(f"/api/v1/tests/{test_id}/attempts", json={})).json()["attempt"]["attempt_id"]
    assert first == second
    await client.post(f"/api/v1/attempts/{first}/start")
    third = (await client.post(f"/api/v1/tests/{test_id}/attempts", json={})).json()["attempt"]
    assert third["attempt_id"] == first and third["status"] == "in_progress"


async def test_another_student_cannot_read_or_write_someone_elses_attempt(client, who, enroll, make_question, make_test):
    test_id, q1, _ = await module_test(make_question, make_test)
    await enroll()
    attempt_id = await start(client, who, test_id)
    who.student(user_id=1755000000007102)
    assert (await client.get(f"/api/v1/attempts/{attempt_id}")).status_code == 404
    assert (await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "b"}})).status_code == 404
    assert (await client.post(f"/api/v1/attempts/{attempt_id}/submit")).status_code == 404
    assert (await client.get(f"/api/v1/attempts/{attempt_id}/result")).status_code == 404


async def test_resuming_is_logged_and_returns_the_saved_answers(client, who, enroll, make_question, make_test, sessionmaker):
    test_id, q1, _ = await module_test(make_question, make_test)
    await enroll()
    attempt_id = await start(client, who, test_id)
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "b"}, "revision": 1})
    await paper(client, attempt_id)
    resumed = await paper(client, attempt_id)
    assert resumed["attempt"]["resume_count"] == 2
    async with sessionmaker() as db:
        types = [e.event_type for e in (await db.execute(select(AttemptEvent).order_by(AttemptEvent.created_at))).scalars()]
    assert types.count("resumed") == 2 and "started" in types


async def test_time_is_up_the_attempt_is_submitted_by_the_server(client, who, enroll, make_question, make_test, expire, work):
    test_id, q1, _ = await module_test(make_question, make_test)
    await enroll()
    attempt_id = await start(client, who, test_id)
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "b"}, "revision": 1})
    await expire(attempt_id)

    late = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "a"}, "revision": 2})
    assert late.status_code == 409 and late.json()["code"] == "ATTEMPT_ENDED"
    state = (await client.get(f"/api/v1/attempts/{attempt_id}")).json()["attempt"]
    assert state["status"] == "submitted" and state["submit_reason"] == "timeout"

    await work.grade()
    result = (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]
    assert result["score"] == 2  # the answer saved before time ran out counts; the late one was refused


async def test_the_worker_submits_attempts_nobody_is_touching(client, who, enroll, make_question, make_test, expire, work):
    test_id, q1, _ = await module_test(make_question, make_test)
    await enroll()
    attempt_id = await start(client, who, test_id)
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "b"}, "revision": 1})
    await expire(attempt_id)
    assert await work.sweep() == 1
    await work.flush()
    await work.grade()
    assert (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]["score"] == 2


async def test_a_paused_attempt_refuses_answers_and_gives_the_stopped_time_back(client, who, enroll, make_question, make_test, sessionmaker):
    test_id, q1, _ = await module_test(make_question, make_test)
    await enroll()
    attempt_id = await start(client, who, test_id)
    async with sessionmaker() as db:
        before = (await db.execute(select(Attempt.deadline_at))).scalar_one()
    who.staff()
    paused = await client.post(f"/api/v1/attempts/{attempt_id}/pause", json={"reason": "Suspicious noise"})
    assert paused.status_code == 200 and paused.json()["attempt"]["status"] == "paused"
    who.student()
    refused = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "b"}})
    assert refused.status_code == 409 and refused.json()["code"] == "ATTEMPT_PAUSED"
    who.staff()
    assert (await client.post(f"/api/v1/attempts/{attempt_id}/unpause")).status_code == 200
    async with sessionmaker() as db:
        after = (await db.execute(select(Attempt.deadline_at))).scalar_one()
    assert after >= before  # the paused seconds were added back
    who.student()
    assert (await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "b"}, "revision": 1})).status_code == 200


async def test_staff_can_terminate_and_students_cannot_control_attempts(client, who, enroll, make_question, make_test):
    test_id, *_ = await module_test(make_question, make_test)
    await enroll()
    attempt_id = await start(client, who, test_id)
    assert (await client.post(f"/api/v1/attempts/{attempt_id}/pause", json={})).status_code == 403  # the student themself
    who.staff(user_id=1755000000007109, organization_id=1755000000007004)  # staff of another institution
    assert (await client.post(f"/api/v1/attempts/{attempt_id}/terminate", json={})).status_code == 404
    who.staff()
    terminated = await client.post(f"/api/v1/attempts/{attempt_id}/terminate", json={"reason": "Cheating"})
    assert terminated.json()["attempt"]["status"] == "submitted" and terminated.json()["attempt"]["submit_reason"] == "terminated"
    events = (await client.get(f"/api/v1/attempts/{attempt_id}/events")).json()["events"]
    assert "terminated" in [e["event_type"] for e in events]


async def test_pools_give_each_student_their_own_reproducible_question_set(client, who, enroll, make_question, make_test, sessionmaker):
    for n in range(8):
        await make_question(mcq(text=f"Pool question {n}", skills=["js"]))
    test_id = await make_test([pool(3, marks=1, skills=["js"])], kind="module", target_id=str(MODULE), shuffle_questions=True, shuffle_options=True)
    await enroll()
    await enroll(1755000000007102, enrollment_id=1755000000008006)
    sets, orders = [], []
    for student in (1755000000007101, 1755000000007102):
        attempt_id = await start(client, who, test_id, student)
        questions = (await paper(client, attempt_id))["questions"]
        assert len(questions) == 3 and len({q["question_id"] for q in questions}) == 3
        sets.append(frozenset(q["question_id"] for q in questions))
        orders.append([o["id"] for q in questions for o in q["body"]["options"]])
    assert sets[0] != sets[1] or orders[0] != orders[1]  # overwhelmingly likely to differ; the seed makes each reproducible
    who.student(1755000000007102)
    again = await client.post(f"/api/v1/attempts/{attempt_id}/resume")
    assert frozenset(q["question_id"] for q in again.json()["questions"]) == sets[1]  # a resume never reshuffles


async def test_match_and_ordering_are_always_presented_shuffled(client, who, enroll, make_question, make_test):
    items = [{"id": f"i{n}", "text": str(n)} for n in range(1, 7)]
    ordering = await make_question({"question_type": "ordering", "text": "Order them", "body": {"items": items}, "answer_key": {"order": [i["id"] for i in items]}})
    test_id = await make_test([fixed(ordering, 1)], kind="module", target_id=str(MODULE))
    await enroll()
    attempt_id = await start(client, who, test_id)
    shown = [i["id"] for i in (await paper(client, attempt_id))["questions"][0]["body"]["items"]]
    assert sorted(shown) == [i["id"] for i in items] and shown != [i["id"] for i in items]


async def test_direct_mode_writes_answers_straight_to_the_database(client, who, enroll, make_question, make_test, settings, sessionmaker):
    settings.ANSWER_BUFFER = "direct"
    test_id, q1, _ = await module_test(make_question, make_test)
    await enroll()
    attempt_id = await start(client, who, test_id)
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "b"}, "revision": 1})
    async with sessionmaker() as db:
        assert (await db.execute(select(AttemptAnswer))).scalar_one().response == {"selected": "b"}
