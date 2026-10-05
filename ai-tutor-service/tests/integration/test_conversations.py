from datetime import timedelta

from sqlalchemy import select, update

from app.core.time import utcnow
from app.models.conversation import Conversation, Message
from tests.conftest import COURSE, NOTES_LOOPS, NOTES_RECURSION, STUDENT_2, ask, start_conversation


async def test_a_learning_conversation_needs_a_course_the_student_is_enrolled_in(client, who, course):
    who.student()
    missing = await client.post("/api/v1/conversations", json={"mode": "learning"})
    assert missing.status_code == 422 and missing.json()["code"] == "COURSE_REQUIRED"
    other = await client.post("/api/v1/conversations", json={"mode": "learning", "course_id": "1755000000029999"})
    assert other.status_code == 403 and other.json()["code"] == "NOT_ENROLLED"
    who.student(STUDENT_2)
    not_enrolled = await client.post("/api/v1/conversations", json={"mode": "learning", "course_id": str(COURSE)})
    assert not_enrolled.status_code == 403


async def test_only_students_use_the_tutor(client, who, course):
    who.staff()
    assert (await client.post("/api/v1/conversations", json={"mode": "support"})).status_code == 403


async def test_a_grounded_answer_is_built_from_numbered_sources_and_cites_the_lesson(client, who, course, gateway):
    who.student()
    conversation = await start_conversation(client)
    response = await ask(client, conversation, "What is a base case in recursion?")
    assert response.status_code == 200, response.text
    turn = response.json()["turn"]
    answer = turn["assistant_message"]
    assert answer["kind"] == "answer" and answer["content"] == "Recursion means a function calls itself [1]."
    assert answer["retrieval"] == "dense" and answer["confidence"] > 0.3
    citation = answer["citations"][0]
    assert (citation["type"], citation["item_id"], citation["item_title"], citation["topic_title"], citation["implicit"]) == ("lesson", str(NOTES_RECURSION), "Recursion basics", "Functions", False)

    call = gateway.tutor_calls()[0]
    assert call["prompt_key"] == "tutor.learning" and call["service"] == "ai-tutor-service" and call["organization_id"] == "1755000000020001"
    assert call["variables"]["course_title"] == "Python Foundations" and "hint_policy" in call["variables"]
    content = call["messages"][-1]["content"]
    assert content.startswith("SOURCES") and "[1] Basics > Functions > Recursion basics" in content and content.endswith("QUESTION:\nWhat is a base case in recursion?")


async def test_an_answer_that_cites_nothing_still_points_at_its_best_source(client, who, course, gateway):
    who.student()
    conversation = await start_conversation(client)
    gateway.reply("A function that calls itself, with a base case.")
    answer = (await ask(client, conversation, "Explain recursion and the base case")).json()["turn"]["assistant_message"]
    assert answer["citations"][0]["implicit"] is True and answer["citations"][0]["item_id"] == str(NOTES_RECURSION)


async def test_the_model_can_cite_a_specific_source(client, who, course, gateway):
    who.student()
    conversation = await start_conversation(client)
    gateway.reply("Loops repeat code [1].")
    answer = (await ask(client, conversation, "How does a while loop repeat code?")).json()["turn"]["assistant_message"]
    assert [c["item_id"] for c in answer["citations"]] == [str(NOTES_LOOPS)]


async def test_earlier_turns_are_sent_as_alternating_history(client, who, course, gateway):
    who.student()
    conversation = await start_conversation(client)
    await ask(client, conversation, "What is a base case in recursion?")
    await ask(client, conversation, "And what is the recursive case?")
    roles = [m["role"] for m in gateway.tutor_calls()[1]["messages"]]
    assert roles == ["user", "assistant", "user"]
    assert gateway.tutor_calls()[1]["messages"][1]["content"] == "Recursion means a function calls itself [1]."


async def test_a_conversation_is_listed_read_back_and_owned_by_its_student(client, who, course):
    who.student()
    conversation = await start_conversation(client)
    await ask(client, conversation, "What is a base case in recursion?")
    listed = (await client.get("/api/v1/conversations")).json()["conversations"]
    assert [c["conversation_id"] for c in listed] == [conversation] and listed[0]["message_count"] == 2
    assert listed[0]["title"] == "What is a base case in recursion?"
    detail = (await client.get(f"/api/v1/conversations/{conversation}")).json()["conversation"]
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]

    who.student(STUDENT_2)
    assert (await client.get(f"/api/v1/conversations/{conversation}")).status_code == 404
    assert (await ask(client, conversation, "hello")).status_code == 404
    assert (await client.get("/api/v1/conversations")).json()["conversations"] == []


async def test_deleting_a_conversation_hides_it_and_housekeeping_removes_it_for_good(client, who, course, sessionmaker, settings):
    from app.worker.runner import housekeeping_once

    who.student()
    conversation = await start_conversation(client)
    await ask(client, conversation, "What is a base case in recursion?")
    assert (await client.delete(f"/api/v1/conversations/{conversation}")).status_code == 204
    assert (await client.get(f"/api/v1/conversations/{conversation}")).status_code == 404
    assert (await client.get("/api/v1/conversations")).json()["conversations"] == []
    async with sessionmaker() as db:
        assert (await db.execute(select(Conversation))).scalars().first() is not None  # still there through the grace period
        await db.execute(update(Conversation).values(deleted_at=utcnow() - timedelta(days=8)))
        await db.commit()
    await housekeeping_once(sessionmaker, settings)
    async with sessionmaker() as db:
        assert (await db.execute(select(Conversation))).scalars().first() is None
        assert (await db.execute(select(Message))).scalars().first() is None


async def test_old_conversations_are_removed_after_the_retention_period(client, who, course, sessionmaker, settings):
    from app.worker.runner import housekeeping_once

    who.student()
    await start_conversation(client)
    async with sessionmaker() as db:
        await db.execute(update(Conversation).values(created_at=utcnow() - timedelta(days=settings.CONVERSATION_RETENTION_DAYS + 1)))
        await db.commit()
    assert (await housekeeping_once(sessionmaker, settings))[1] == 1


async def test_a_retried_message_with_the_same_idempotency_key_is_answered_once(client, who, course, gateway):
    who.student()
    conversation = await start_conversation(client)
    first = await ask(client, conversation, "What is a base case in recursion?", key="retry-key-0001")
    second = await ask(client, conversation, "What is a base case in recursion?", key="retry-key-0001")
    assert first.json()["turn"]["assistant_message"]["message_id"] == second.json()["turn"]["assistant_message"]["message_id"]
    assert len(gateway.tutor_calls()) == 1
    detail = (await client.get(f"/api/v1/conversations/{conversation}")).json()["conversation"]
    assert detail["message_count"] == 2


async def test_a_message_is_kept_when_the_answer_fails_and_the_retry_completes_the_same_turn(client, who, course, gateway):
    who.student()
    conversation = await start_conversation(client)
    gateway.completion_error = (502, "PROVIDER_UNAVAILABLE")
    failed = await ask(client, conversation, "What is a base case in recursion?", key="retry-key-0002")
    assert failed.status_code == 503 and failed.json()["code"] == "TUTOR_UNAVAILABLE"
    assert (await client.get(f"/api/v1/conversations/{conversation}")).json()["conversation"]["message_count"] == 1

    gateway.completion_error = None
    retried = await ask(client, conversation, "What is a base case in recursion?", key="retry-key-0002")
    assert retried.status_code == 200
    detail = (await client.get(f"/api/v1/conversations/{conversation}")).json()["conversation"]
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]  # the student's message was not saved twice


async def test_an_exhausted_quota_and_a_disabled_organization_are_reported_plainly(client, who, course, gateway):
    who.student()
    conversation = await start_conversation(client)
    gateway.embedding_error = (429, "TOKEN_QUOTA_EXCEEDED")
    quota = await ask(client, conversation, "What is a base case in recursion?")
    assert quota.status_code == 429 and quota.json()["code"] == "QUOTA_EXCEEDED"
    gateway.embedding_error = (403, "ORG_SUSPENDED")
    disabled = await ask(client, conversation, "What is a base case in recursion?")
    assert disabled.status_code == 403 and disabled.json()["code"] == "TUTOR_DISABLED_FOR_ORGANIZATION"


async def test_without_embeddings_the_tutor_falls_back_to_word_overlap_and_says_so(client, who, course, gateway):
    who.student()
    conversation = await start_conversation(client)
    gateway.embedding_error = (503, "PROVIDER_UNAVAILABLE")
    answer = (await ask(client, conversation, "what is a base case in recursion")).json()["turn"]["assistant_message"]
    assert answer["retrieval"] == "lexical" and answer["citations"][0]["item_id"] == str(NOTES_RECURSION)


async def test_a_message_over_the_length_limit_is_rejected(client, who, course):
    who.student()
    conversation = await start_conversation(client)
    assert (await ask(client, conversation, "x" * 4001)).status_code == 422
