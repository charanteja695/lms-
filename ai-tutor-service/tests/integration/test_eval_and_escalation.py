from datetime import timedelta

from sqlalchemy import select, update

from app.core.time import utcnow
from app.models.conversation import Escalation
from app.models.outbox_event import OutboxEvent
from tests.conftest import COURSE, NOTES_LOOPS, NOTES_RECURSION, STUDENT, VERSION, ask, start_conversation


# ---------------------------------------------------------------- offline evaluation
async def _eval_set(client, who) -> str:
    who.author()
    created = await client.post("/api/v1/eval-sets", json={"course_id": str(COURSE), "name": "Week 1 questions"})
    assert created.status_code == 201
    return created.json()["eval_set"]["eval_set_id"]


async def _case(client, eval_set: str, question: str, *items: int):
    response = await client.post(f"/api/v1/eval-sets/{eval_set}/cases", json={"question": question, "expected_item_ids": [str(i) for i in items]})
    assert response.status_code == 201, response.text


async def test_an_evaluation_run_measures_whether_the_right_lesson_is_retrieved(client, who, course):
    eval_set = await _eval_set(client, who)
    await _case(client, eval_set, "What is a base case in recursion?", NOTES_RECURSION)
    await _case(client, eval_set, "How does a while loop repeat code?", NOTES_LOOPS)
    await _case(client, eval_set, "Explain quantum entanglement", NOTES_LOOPS)  # a question the course cannot answer: expected to miss
    run = (await client.post(f"/api/v1/eval-sets/{eval_set}/runs", json={"top_k": 1})).json()["run"]
    assert (run["method"], run["case_count"], run["version_id"], run["top_k"]) == ("dense", 3, str(VERSION), 1)
    assert run["hits"] == 2 and run["hit_rate"] == 0.6667 and run["mrr"] == 0.8333
    by_question = {r["question"]: r for r in run["results"]}
    assert by_question["What is a base case in recursion?"]["rank"] == 1 and by_question["What is a base case in recursion?"]["hit"] is True
    assert by_question["Explain quantum entanglement"]["hit"] is False
    assert by_question["What is a base case in recursion?"]["top"][0]["item_title"] == "Recursion basics"

    detail = (await client.get(f"/api/v1/eval-sets/{eval_set}")).json()
    assert len(detail["cases"]) == 3 and detail["runs"][0]["run_id"] == run["run_id"]
    assert (await client.get(f"/api/v1/eval-runs/{run['run_id']}")).json()["run"]["hits"] == 2


async def test_an_evaluation_falls_back_to_word_overlap_when_embeddings_are_down(client, who, course, gateway):
    eval_set = await _eval_set(client, who)
    await _case(client, eval_set, "what is a base case in recursion", NOTES_RECURSION)
    gateway.embedding_error = (503, "PROVIDER_UNAVAILABLE")
    run = (await client.post(f"/api/v1/eval-sets/{eval_set}/runs", json={})).json()["run"]
    assert run["method"] == "lexical" and run["hits"] == 1


async def test_evaluation_input_is_validated(client, who, course):
    eval_set = await _eval_set(client, who)
    assert (await client.post(f"/api/v1/eval-sets/{eval_set}/runs", json={})).json()["code"] == "EMPTY_EVAL_SET"
    unknown = await client.post(f"/api/v1/eval-sets/{eval_set}/cases", json={"question": "Q?", "expected_item_ids": ["1755000000029999"]})
    assert unknown.status_code == 422 and unknown.json()["code"] == "UNKNOWN_ITEM"
    await _case(client, eval_set, "What is recursion?", NOTES_RECURSION)
    wrong_version = await client.post(f"/api/v1/eval-sets/{eval_set}/runs", json={"version_id": "1755000000029998"})
    assert wrong_version.status_code == 422 and wrong_version.json()["code"] == "VERSION_NOT_IN_COURSE"


async def test_a_course_that_has_not_been_published_has_no_lessons_to_name_or_evaluate(client, who):
    eval_set = await _eval_set(client, who)
    assert (await client.post(f"/api/v1/eval-sets/{eval_set}/cases", json={"question": "Q?", "expected_item_ids": [str(NOTES_RECURSION)]})).status_code == 422
    assert (await client.post(f"/api/v1/eval-sets/{eval_set}/runs", json={})).json()["code"] == "EMPTY_EVAL_SET"


async def test_a_course_lists_its_evaluation_sets_newest_first(client, who, course):
    first = await _eval_set(client, who)
    second = (await client.post("/api/v1/eval-sets", json={"course_id": str(COURSE), "name": "Week 2 questions"})).json()["eval_set"]["eval_set_id"]
    listed = (await client.get("/api/v1/eval-sets", params={"course_id": str(COURSE)})).json()["eval_sets"]
    assert [s["eval_set_id"] for s in listed] == [second, first]
    assert (await client.get("/api/v1/eval-sets", params={"course_id": "1755000000029997"})).json()["eval_sets"] == []


async def test_evaluation_is_for_authors_only(client, who, course):
    who.student()
    assert (await client.post("/api/v1/eval-sets", json={"course_id": str(COURSE), "name": "x"})).status_code == 403
    assert (await client.get("/api/v1/eval-sets", params={"course_id": str(COURSE)})).status_code == 403
    who.staff()
    assert (await client.post("/api/v1/eval-sets", json={"course_id": str(COURSE), "name": "x"})).status_code == 403


# ---------------------------------------------------------------- escalation delivery
async def _escalate(client, who, text: str = "I want a refund for this course") -> str:
    who.student()
    conversation = await start_conversation(client)
    turn = (await ask(client, conversation, text)).json()["turn"]
    return turn["escalation"]["escalation_id"]


async def test_the_worker_opens_a_ticket_with_a_model_written_hand_off_note(client, who, course, deliver_now, support, gateway, sessionmaker):
    escalation_id = await _escalate(client, who)
    assert await deliver_now() == 1
    ticket = support.tickets[0]
    assert ticket["category"] == "billing" and ticket["source"] == "ai-tutor" and ticket["requester_user_id"] == str(STUDENT)
    assert ticket["organization_id"] == "1755000000020001" and ticket["course_id"] == str(COURSE) and ticket["reason"] == "sensitive_topic"
    assert ticket["description"].startswith("Summary for the agent.") and "Course: Python Foundations" in ticket["description"] and ticket["source_ref"]
    assert gateway.completions[-1]["prompt_key"] == "tutor.escalation_summary" and "Student: I want a refund" in gateway.completions[-1]["messages"][0]["content"]
    async with sessionmaker() as db:
        row = (await db.execute(select(Escalation))).scalar_one()
        assert row.status == "created" and row.ticket_id and str(row.public_id) == escalation_id
    assert await deliver_now() == 0  # nothing left


async def test_the_event_is_announced_when_the_hand_off_is_recorded(client, who, course, sessionmaker):
    await _escalate(client, who)
    async with sessionmaker() as db:
        event = (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == "tutor.escalated"))).scalar_one()
        assert event.payload["category"] == "billing" and event.payload["student_user_id"] == str(STUDENT) and event.payload["course_id"] == str(COURSE)


async def test_when_the_summary_model_is_down_the_hand_off_still_goes_out_with_a_plain_summary(client, who, course, deliver_now, support, gateway):
    await _escalate(client, who)
    gateway.summary_error = True
    await deliver_now()
    assert "The student's last message: \"I want a refund for this course\"" in support.tickets[0]["description"]


async def test_a_support_outage_is_retried_with_backoff_and_never_opens_two_tickets(client, who, course, deliver_now, support, sessionmaker):
    await _escalate(client, who)
    support.fail_with = 503
    await deliver_now()
    async with sessionmaker() as db:
        row = (await db.execute(select(Escalation))).scalar_one()
        assert row.status == "pending" and row.attempts == 1 and row.next_attempt_at > utcnow() and row.last_error and row.summary
    assert await deliver_now() == 0  # not due yet

    support.fail_with = None
    async with sessionmaker() as db:
        await db.execute(update(Escalation).values(next_attempt_at=utcnow() - timedelta(seconds=1)))
        await db.commit()
    await deliver_now()
    assert len(support.tickets) == 1
    async with sessionmaker() as db:
        assert (await db.execute(select(Escalation))).scalar_one().status == "created"


async def test_a_ticket_that_can_never_be_created_is_marked_failed_and_a_manager_can_retry_it(client, who, course, deliver_now, support, sessionmaker):
    escalation_id = await _escalate(client, who)
    support.fail_with = 422
    await deliver_now()
    async with sessionmaker() as db:
        assert (await db.execute(select(Escalation))).scalar_one().status == "failed"

    who.support_manager()
    listed = (await client.get("/api/v1/escalations", params={"status": "failed"})).json()["escalations"]
    assert [e["escalation_id"] for e in listed] == [escalation_id] and listed[0]["last_error"].startswith("rejected")
    support.fail_with = None
    assert (await client.post(f"/api/v1/escalations/{escalation_id}/retry")).json()["escalation"]["status"] == "pending"
    await deliver_now()
    assert len(support.tickets) == 1
    assert (await client.post(f"/api/v1/escalations/{escalation_id}/retry")).status_code == 409  # only a failed one can be retried


async def test_an_abandoned_claim_is_picked_up_again_after_its_lease(client, who, course, deliver_now, sessionmaker, support):
    await _escalate(client, who)
    async with sessionmaker() as db:
        await db.execute(update(Escalation).values(lease_until=utcnow() + timedelta(seconds=30)))
        await db.commit()
    assert await deliver_now() == 0  # someone else holds it
    async with sessionmaker() as db:
        await db.execute(update(Escalation).values(lease_until=utcnow() - timedelta(seconds=1)))
        await db.commit()
    assert await deliver_now() == 1 and len(support.tickets) == 1


async def test_escalations_are_visible_only_to_support_managers(client, who, course):
    await _escalate(client, who)
    for identity in (who.student, who.staff, who.author):
        identity()
        assert (await client.get("/api/v1/escalations")).status_code == 403
    who.support_manager()
    assert len((await client.get("/api/v1/escalations")).json()["escalations"]) == 1


async def test_support_service_can_read_the_conversation_behind_a_ticket(client, who, course, internal_headers):
    who.student()
    conversation = await start_conversation(client)
    await ask(client, conversation, "What is a base case in recursion?")
    transcript = await client.get(f"/api/v1/internal/conversations/{conversation}", headers=internal_headers)
    assert transcript.status_code == 200 and [m["role"] for m in transcript.json()["conversation"]["messages"]] == ["user", "assistant"]
    assert (await client.get(f"/api/v1/internal/conversations/{conversation}")).status_code == 403
    assert (await client.get("/api/v1/internal/conversations/1755000000029999", headers=internal_headers)).status_code == 404
