import json

from sqlalchemy import func, select

from app.models.conversation import Message
from tests.conftest import COURSE, ENROLLMENT, ORG_A, STUDENT, STUDENT_2, VERSION, ask, start_conversation


async def test_the_support_assistant_answers_from_read_only_facts_about_the_students_own_account(client, who, course, send_event, gateway):
    await send_event("attempt.finalized", {"attempt_id": "1755000000050001", "user_id": str(STUDENT), "test_kind": "final", "course_id": str(COURSE), "result": "passed", "percent": 82.5})
    await send_event("certificate.issued", {"certificate_id": "1755000000050002", "student_user_id": str(STUDENT), "course_id": str(COURSE), "grade": "Distinction", "issued_at": "2026-09-20T10:00:00Z"})
    await send_event("attempt.finalized", {"attempt_id": "1755000000050003", "user_id": str(STUDENT_2), "test_kind": "module", "result": "failed", "percent": 10})
    who.student()
    conversation = await start_conversation(client, mode="support", course_id=None)
    turn = (await ask(client, conversation, "Is my enrolment active, did I pass the test and do I have my certificate?")).json()["turn"]
    assert turn["assistant_message"]["kind"] == "answer"
    call = gateway.tutor_calls()[0]
    assert call["prompt_key"] == "tutor.support" and call["variables"] == {}
    facts = call["messages"][-1]["content"]
    assert "FACTS ABOUT THIS STUDENT" in facts and "Python Foundations — active" in facts
    assert "Test attempt (final): finalized, result passed (82%)" in facts
    assert "Certificate: issued, grade Distinction" in facts
    assert "failed" not in facts and "10%" not in facts  # another student's attempt is never shown
    assert "tools" not in call  # the model is offered no tools; lookups are made by the service, read-only


async def test_a_removed_enrolment_is_reported_as_removed_and_a_revoked_certificate_as_revoked(client, who, course, send_event, gateway):
    await send_event("enrollment.removed", {"enrollment_id": str(ENROLLMENT), "student_user_id": str(STUDENT), "version_id": str(VERSION)})
    await send_event("certificate.issued", {"certificate_id": "1755000000050002", "student_user_id": str(STUDENT), "course_id": str(COURSE), "grade": "A", "issued_at": "2026-09-20T10:00:00Z"})
    await send_event("certificate.revoked", {"certificate_id": "1755000000050002"})
    who.student()
    conversation = await start_conversation(client, mode="support", course_id=None)
    await ask(client, conversation, "What is the status of my enrolment and my certificate?")
    facts = gateway.tutor_calls()[0]["messages"][-1]["content"]
    assert "Python Foundations — removed" in facts and "Certificate: revoked" in facts


async def test_a_support_question_with_nothing_to_answer_from_is_not_guessed_at(client, who, course, gateway):
    who.student()
    conversation = await start_conversation(client, mode="support", course_id=None)
    turn = (await ask(client, conversation, "What colour is the sky on Mars?")).json()["turn"]
    assert turn["assistant_message"]["kind"] == "low_confidence" and gateway.tutor_calls() == []


async def test_no_lookups_are_made_for_a_question_that_asks_for_none(client, who, course, gateway):
    who.student()
    conversation = await start_conversation(client, mode="support", course_id=None)
    await ask(client, conversation, "Tell me about certificates and how they work")
    assert "FACTS ABOUT THIS STUDENT" in gateway.tutor_calls()[0]["messages"][-1]["content"]  # "certificate" asks for the certificate lookup
    await ask(client, conversation, "How do I use the video player speed control?")
    assert len(gateway.tutor_calls()) == 1  # nothing matched: no facts, no FAQ, so no model call either


# ---------------------------------------------------------------- streaming
def _events(response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


async def test_a_streamed_answer_arrives_as_deltas_then_the_saved_message(client, who, course, gateway, sessionmaker):
    who.student()
    conversation = await start_conversation(client)
    gateway.reply("Recursion needs a base case [1].")
    response = await ask(client, conversation, "What is a base case in recursion?", stream=True)
    assert response.status_code == 200 and response.headers["content-type"].startswith("application/x-ndjson")
    events = _events(response)
    assert [e["type"] for e in events] == ["start", "delta", "delta", "message"]
    assert "".join(e["text"] for e in events if e["type"] == "delta") == "Recursion needs a base case [1]."
    final = events[-1]["message"]
    assert final["content"] == "Recursion needs a base case [1]." and final["citations"][0]["item_title"] == "Recursion basics" and final["kind"] == "answer"
    assert events[0]["user_message"]["content"] == "What is a base case in recursion?"
    detail = (await client.get(f"/api/v1/conversations/{conversation}")).json()["conversation"]
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"] and detail["messages"][1]["message_id"] == final["message_id"]


async def test_a_stream_that_fails_midway_reports_it_and_saves_no_half_answer(client, who, course, gateway, sessionmaker):
    who.student()
    conversation = await start_conversation(client)
    gateway.stream_error = True
    events = _events(await ask(client, conversation, "What is a base case in recursion?", stream=True))
    assert events[-1]["type"] == "error" and events[-1]["code"] == "TUTOR_UNAVAILABLE"
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count(Message.id)).where(Message.role == "assistant"))).scalar_one() == 0
        assert (await db.execute(select(func.count(Message.id)).where(Message.role == "user"))).scalar_one() == 1


async def test_a_stream_that_needs_no_model_is_a_start_line_and_a_message(client, who, course, gateway):
    who.student()
    conversation = await start_conversation(client)
    events = _events(await ask(client, conversation, "Can I talk to a human?", stream=True))
    assert [e["type"] for e in events] == ["start", "message"] and events[1]["message"]["kind"] == "escalation"
    assert gateway.tutor_calls() == []


async def test_a_moderated_stream_is_a_plain_refusal(client, who, course, gateway):
    who.student()
    conversation = await start_conversation(client)
    gateway.blocked = True
    events = _events(await ask(client, conversation, "What is a base case in recursion?", stream=True))
    assert events[-1]["type"] == "message" and events[-1]["message"]["kind"] == "blocked"


async def test_errors_that_are_http_errors_are_raised_before_a_stream_starts(client, who, course, gateway):
    who.student()
    conversation = await start_conversation(client)
    gateway.embedding_error = (429, "TOKEN_QUOTA_EXCEEDED")
    response = await ask(client, conversation, "What is a base case in recursion?", stream=True)
    assert response.status_code == 429 and response.json()["code"] == "QUOTA_EXCEEDED"


async def test_a_retried_stream_with_the_same_key_replays_the_saved_answer(client, who, course, gateway):
    who.student()
    conversation = await start_conversation(client)
    first = _events(await ask(client, conversation, "What is a base case in recursion?", key="stream-key-001", stream=True))
    second = _events(await ask(client, conversation, "What is a base case in recursion?", key="stream-key-001", stream=True))
    assert second[-1]["message"]["message_id"] == first[-1]["message"]["message_id"] and [e["type"] for e in second] == ["start", "message"]
    assert len(gateway.tutor_calls()) == 1


async def test_state_arrives_from_events_only_for_the_right_student(client, who, course, send_event):
    """An enrolment ends: the student can no longer open a learning conversation for that course."""
    who.student()
    await send_event("enrollment.removed", {"enrollment_id": str(ENROLLMENT), "student_user_id": str(STUDENT), "version_id": str(VERSION)})
    response = await client.post("/api/v1/conversations", json={"mode": "learning", "course_id": str(COURSE)})
    assert response.status_code == 403 and response.json()["code"] == "NOT_ENROLLED"
    await send_event("enrollment.created", {"enrollment_id": str(ENROLLMENT), "student_user_id": str(STUDENT), "organization_id": str(ORG_A), "version_id": str(VERSION)})
    assert (await client.post("/api/v1/conversations", json={"mode": "learning", "course_id": str(COURSE)})).status_code == 201
