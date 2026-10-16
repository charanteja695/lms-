from sqlalchemy import select

from app.models.faq import FaqEntry
from app.models.outbox_event import OutboxEvent
from tests.conftest import COURSE, ORG_A, ORG_B, STAFF_A, STAFF_B, STUDENT, STUDENT_2, ask, start_conversation

QUESTION = "How do I reset my attempt limit?"
ANSWER = "Attempt limits can only be reset by your institution's exam team; ask them through a support request."


async def _publish(client, who, *, scope: str = "platform", organization_id: int | None = None, course_id: int | None = None, question: str = QUESTION) -> str:
    body = {"scope": scope, "question": question, "answer": ANSWER}
    if organization_id:
        body["organization_id"] = str(organization_id)
    if course_id:
        body["course_id"] = str(course_id)
    created = await client.post("/api/v1/faq/manage", json=body)
    assert created.status_code == 201, created.text
    faq_id = created.json()["faq"]["faq_id"]
    assert (await client.post(f"/api/v1/faq/manage/{faq_id}/publish")).status_code == 200
    return faq_id


async def test_a_close_question_is_answered_from_the_faq_without_calling_a_model(client, who, course, gateway):
    who.support_manager()
    faq_id = await _publish(client, who)
    who.student()
    conversation = await start_conversation(client, mode="support", course_id=None)
    answer = (await ask(client, conversation, QUESTION)).json()["turn"]["assistant_message"]
    assert answer["kind"] == "faq" and answer["content"] == ANSWER and answer["citations"][0]["faq_id"] == faq_id
    assert gateway.tutor_calls() == []


async def test_a_draft_or_archived_entry_is_never_used(client, who, course, gateway):
    who.support_manager()
    created = await client.post("/api/v1/faq/manage", json={"scope": "platform", "question": QUESTION, "answer": ANSWER})
    who.student()
    conversation = await start_conversation(client, mode="support", course_id=None)
    assert (await ask(client, conversation, QUESTION)).json()["turn"]["assistant_message"]["kind"] != "faq"
    who.support_manager()
    faq_id = created.json()["faq"]["faq_id"]
    await client.post(f"/api/v1/faq/manage/{faq_id}/publish")
    await client.post(f"/api/v1/faq/manage/{faq_id}/archive")
    who.student()
    assert (await ask(client, conversation, QUESTION)).json()["turn"]["assistant_message"]["kind"] != "faq"


async def test_a_partly_matching_entry_is_handed_to_the_model_as_context(client, who, course, gateway):
    who.support_manager()
    await _publish(client, who)
    who.student()
    conversation = await start_conversation(client, mode="support", course_id=None)
    await ask(client, conversation, "attempt limit reset and cooldown rules please")
    call = gateway.tutor_calls()[0]
    assert call["prompt_key"] == "tutor.support" and "FAQ ENTRIES" in call["messages"][-1]["content"] and ANSWER in call["messages"][-1]["content"]


async def test_faq_entries_are_scoped_to_their_institution_and_course(client, who, course, gateway):
    who.support_manager()
    await _publish(client, who, scope="organization", organization_id=ORG_B, question="Where is the hostel office?")
    await _publish(client, who, scope="course", course_id=COURSE, question="When is the recursion workshop held?")
    who.student()  # in ORG_A, enrolled in COURSE
    visible = {e["question"] for e in (await client.get("/api/v1/faq")).json()["faqs"]}
    assert visible == {"When is the recursion workshop held?"}
    assert {e["question"] for e in (await client.get("/api/v1/faq", params={"q": "recursion workshop"})).json()["faqs"]} == visible
    assert (await client.get("/api/v1/faq", params={"q": "hostel"})).json()["faqs"] == []


async def test_who_may_write_which_scope(client, who):
    platform = {"scope": "platform", "question": "Q?", "answer": "A."}
    org_a = {"scope": "organization", "organization_id": str(ORG_A), "question": "Q?", "answer": "A."}
    course = {"scope": "course", "course_id": str(COURSE), "question": "Q?", "answer": "A."}
    who.student()
    assert (await client.post("/api/v1/faq/manage", json=platform)).status_code == 403
    who.staff()
    assert (await client.post("/api/v1/faq/manage", json=org_a)).status_code == 201
    assert (await client.post("/api/v1/faq/manage", json={**org_a, "organization_id": str(ORG_B)})).status_code == 403
    assert (await client.post("/api/v1/faq/manage", json=platform)).status_code == 403
    who.author()
    assert (await client.post("/api/v1/faq/manage", json=course)).status_code == 201
    assert (await client.post("/api/v1/faq/manage", json=platform)).status_code == 403
    who.support_manager()
    assert (await client.post("/api/v1/faq/manage", json=platform)).status_code == 201


async def test_a_scope_must_carry_what_it_needs(client, who):
    who.support_manager()
    assert (await client.post("/api/v1/faq/manage", json={"scope": "course", "question": "Q?", "answer": "A."})).json()["code"] == "INVALID_SCOPE"
    assert (await client.post("/api/v1/faq/manage", json={"scope": "platform", "course_id": str(COURSE), "question": "Q?", "answer": "A."})).json()["code"] == "INVALID_SCOPE"


async def test_editing_a_published_entry_keeps_it_answerable_and_a_staff_member_cannot_touch_another_institutions(client, who):
    who.staff()
    faq_id = await _publish(client, who, scope="organization", organization_id=ORG_A)
    edited = await client.patch(f"/api/v1/faq/manage/{faq_id}", json={"answer": "New answer."})
    assert edited.json()["faq"]["answer"] == "New answer." and edited.json()["faq"]["status"] == "published"
    who.staff(STAFF_B, organization_id=ORG_B)
    assert (await client.patch(f"/api/v1/faq/manage/{faq_id}", json={"answer": "hijack"})).status_code == 403
    assert (await client.post(f"/api/v1/faq/manage/{faq_id}/archive")).status_code == 403
    listed = (await client.get("/api/v1/faq/manage")).json()["faqs"]
    assert listed == []  # staff of ORG_B see only ORG_B's own entries


async def test_publishing_still_works_when_the_embedding_service_is_down(client, who, gateway):
    who.support_manager()
    gateway.embedding_error = (503, "PROVIDER_UNAVAILABLE")
    faq_id = await _publish(client, who)
    assert (await client.get("/api/v1/faq/manage", params={"status": "published"})).json()["faqs"][0]["faq_id"] == faq_id


async def test_staff_promote_a_good_answer_to_a_draft_and_edit_it_before_publishing(client, who, course, gateway):
    who.student()
    conversation = await start_conversation(client)
    answer = (await ask(client, conversation, "What is a base case in recursion?")).json()["turn"]["assistant_message"]
    who.staff(STAFF_B, organization_id=ORG_B)
    assert (await client.post("/api/v1/faq/manage/promote", json={"message_id": answer["message_id"]})).status_code == 403
    who.staff()
    promoted = await client.post("/api/v1/faq/manage/promote", json={"message_id": answer["message_id"]})
    assert promoted.status_code == 201
    faq = promoted.json()["faq"]
    assert (faq["scope"], faq["status"], faq["question"], faq["course_id"]) == ("organization", "draft", "What is a base case in recursion?", None)  # staff write for their own institution
    assert faq["answer"] == answer["content"]


async def test_the_promoted_entry_of_an_unknown_message_is_a_404(client, who):
    who.support_manager()
    assert (await client.post("/api/v1/faq/manage/promote", json={"message_id": "1755000000029990"})).status_code == 404


# ---------------------------------------------------------------- feedback
async def test_a_student_rates_an_answer_and_can_change_their_mind(client, who, course, sessionmaker):
    who.student()
    conversation = await start_conversation(client)
    answer = (await ask(client, conversation, "What is a base case in recursion?")).json()["turn"]["assistant_message"]
    up = await client.post(f"/api/v1/messages/{answer['message_id']}/feedback", json={"rating": "up"})
    assert up.status_code == 200 and up.json()["feedback"]["rating"] == "up"
    down = await client.post(f"/api/v1/messages/{answer['message_id']}/feedback", json={"rating": "down", "comment": "It missed the recursive case."})
    assert down.json()["feedback"] == {"message_id": answer["message_id"], "rating": "down", "comment": "It missed the recursive case."}
    async with sessionmaker() as db:
        events = (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == "tutor.feedback"))).scalars().all()
        assert [e.payload["rating"] for e in events] == ["up", "down"] and events[0].payload["course_id"] == str(COURSE)


async def test_only_the_owner_can_rate_and_only_assistant_answers(client, who, course):
    who.student()
    conversation = await start_conversation(client)
    turn = (await ask(client, conversation, "What is a base case in recursion?")).json()["turn"]
    who.student(STUDENT_2)
    assert (await client.post(f"/api/v1/messages/{turn['assistant_message']['message_id']}/feedback", json={"rating": "up"})).status_code == 404
    who.student()
    assert (await client.post(f"/api/v1/messages/{turn['user_message']['message_id']}/feedback", json={"rating": "up"})).status_code == 404


async def test_a_thumbs_up_on_a_faq_answer_ranks_that_entry_higher(client, who, course, sessionmaker):
    who.support_manager()
    await _publish(client, who)
    who.student()
    conversation = await start_conversation(client, mode="support", course_id=None)
    answer = (await ask(client, conversation, QUESTION)).json()["turn"]["assistant_message"]
    await client.post(f"/api/v1/messages/{answer['message_id']}/feedback", json={"rating": "up"})
    await client.post(f"/api/v1/messages/{answer['message_id']}/feedback", json={"rating": "up"})  # not counted twice
    async with sessionmaker() as db:
        assert (await db.execute(select(FaqEntry))).scalar_one().helpful_count == 1
    await client.post(f"/api/v1/messages/{answer['message_id']}/feedback", json={"rating": "down"})
    async with sessionmaker() as db:
        assert (await db.execute(select(FaqEntry))).scalar_one().helpful_count == 0


async def test_authors_see_totals_and_the_unhelpful_answers_without_who_asked(client, who, course):
    who.student()
    conversation = await start_conversation(client)
    turn = (await ask(client, conversation, "What is a base case in recursion?")).json()["turn"]
    await client.post(f"/api/v1/messages/{turn['assistant_message']['message_id']}/feedback", json={"rating": "down", "comment": "Too vague"})
    second = (await ask(client, conversation, "What is a for loop?")).json()["turn"]
    await client.post(f"/api/v1/messages/{second['assistant_message']['message_id']}/feedback", json={"rating": "up"})

    who.author()
    summary = (await client.get("/api/v1/feedback/summary", params={"course_id": str(COURSE)})).json()["summary"]
    assert (summary["up"], summary["down"], summary["down_rate"]) == (1, 1, 0.5)
    items = (await client.get("/api/v1/feedback/downvoted", params={"course_id": str(COURSE)})).json()["items"]
    assert len(items) == 1 and items[0]["question"] == "What is a base case in recursion?" and items[0]["comment"] == "Too vague"
    assert str(STUDENT) not in str(items) and str(ORG_A) not in str(items)
    who.student()
    assert (await client.get("/api/v1/feedback/summary", params={"course_id": str(COURSE)})).status_code == 403


async def test_the_tutor_and_the_faq_follow_the_persons_permissions(client, act_as):
    """A super admin can stop one student using the tutor, or let one student write their institution's FAQ."""
    act_as(STUDENT, role="student", organization_id=ORG_A, defaults=False)
    assert (await client.post("/api/v1/conversations", json={"course_id": str(COURSE)})).status_code == 403
    entry = {"scope": "organization", "organization_id": str(ORG_A), "question": "When is the lab open?", "answer": "Weekdays, 9 to 5."}
    act_as(STUDENT, role="student", organization_id=ORG_A, scopes=("tutor.faq.manage",))
    assert (await client.post("/api/v1/faq/manage", json=entry)).status_code == 201
    act_as(STAFF_A, role="staff", organization_id=ORG_A, defaults=False)
    assert (await client.post("/api/v1/faq/manage", json=entry)).status_code == 403
