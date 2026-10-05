from sqlalchemy import select

from app.models.outbox_event import OutboxEvent
from tests.conftest import fixed, mcq, pool, true_false


async def events(sessionmaker, event_type: str) -> list[dict]:
    async with sessionmaker() as db:
        rows = (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == event_type).order_by(OutboxEvent.created_at))).scalars()
        return [row.payload for row in rows]


async def test_create_a_test_with_fixed_and_pool_slots_and_read_it_back(client, who, make_question):
    q1 = await make_question(mcq(), default_marks=2)
    who.author()
    response = await client.post(
        "/api/v1/tests",
        json={
            "title": "JS basics",
            "kind": "practice",
            "duration_minutes": 20,
            "sections": [{"title": "Part A", "slots": [fixed(q1), pool(3, marks=1.5, difficulty_min=2, skills=["js"])]}],
        },
    )
    assert response.status_code == 201, response.text
    test = response.json()["test"]
    assert test["status"] == "draft" and test["total_marks"] is None
    slots = test["sections"][0]["slots"]
    assert slots[0]["question_id"] == q1 and slots[0]["marks"] == 2  # defaults to the question's marks
    assert slots[1]["slot_type"] == "pool" and slots[1]["count"] == 3 and slots[1]["criteria"]["skills"] == ["js"]


async def test_validation_lists_what_blocks_publishing(client, who, make_question):
    await make_question(mcq(skills=["js"]))
    who.author()
    created = await client.post(
        "/api/v1/tests",
        json={"title": "T", "kind": "practice", "sections": [{"title": "A", "slots": [pool(5, skills=["js"])]}]},  # no duration, pool too small
    )
    test_id = created.json()["test"]["test_id"]
    result = (await client.get(f"/api/v1/tests/{test_id}/validation")).json()
    assert result["valid"] is False
    codes = {(i["field"], i["code"]) for i in result["issues"]}
    assert ("duration_minutes", "REQUIRED") in codes
    assert ("sections[1].slots[1]", "POOL_TOO_SMALL") in codes
    refused = await client.post(f"/api/v1/tests/{test_id}/submit")
    assert refused.status_code == 422 and len(refused.json()["details"]) == 2


async def test_publishing_freezes_the_test_totals_and_emits_test_published(client, who, make_test, make_question, sessionmaker):
    q1, q2 = await make_question(), await make_question(true_false())
    test_id = await make_test([fixed(q1, 2), fixed(q2, 3)], kind="module", target_id="1755000000000222")
    who.author()
    test = (await client.get(f"/api/v1/tests/{test_id}")).json()["test"]
    assert test["status"] == "published" and test["total_marks"] == 5 and test["question_count"] == 2
    assert test["target_type"] == "module" and test["target_id"] == "1755000000000222"

    (payload,) = await events(sessionmaker, "test.published")
    # catalog-service's consumer reads exactly these three keys (its media_events.handle_test_published)
    assert payload["target_type"] == "module" and payload["target_id"] == "1755000000000222" and payload["test_id"] == test_id


async def test_a_published_test_cannot_be_edited_but_can_be_cloned(client, who, make_test, make_question):
    q1 = await make_question()
    test_id = await make_test([fixed(q1)])
    who.author()
    assert (await client.patch(f"/api/v1/tests/{test_id}", json={"title": "New"})).status_code == 409
    assert (await client.put(f"/api/v1/tests/{test_id}/sections", json={"sections": [{"title": "X", "slots": [fixed(q1)]}]})).status_code == 409
    clone = await client.post(f"/api/v1/tests/{test_id}/clone")
    assert clone.status_code == 201
    copy = clone.json()["test"]
    assert copy["status"] == "draft" and copy["title"].endswith("(copy)") and copy["test_id"] != test_id
    assert copy["sections"][0]["slots"][0]["question_id"] == q1


async def test_only_one_published_test_per_target_until_the_old_one_is_retired(client, who, make_test, make_question):
    q1 = await make_question()
    first = await make_test([fixed(q1)], kind="topic", target_id="1755000000000333")
    who.author()
    second = (await client.post(f"/api/v1/tests/{first}/clone")).json()["test"]["test_id"]
    await client.post(f"/api/v1/tests/{second}/submit")
    who.reviewer()
    refused = await client.post(f"/api/v1/tests/{second}/approve", json={})
    assert refused.status_code == 409 and refused.json()["code"] == "TARGET_ALREADY_HAS_TEST"
    assert (await client.post(f"/api/v1/tests/{first}/retire")).status_code == 200
    assert (await client.post(f"/api/v1/tests/{second}/approve", json={})).status_code == 200


async def test_a_topic_test_needs_its_target(client, who, make_question):
    q1 = await make_question()
    who.author()
    created = await client.post("/api/v1/tests", json={"title": "T", "kind": "topic", "duration_minutes": 10, "sections": [{"title": "A", "slots": [fixed(q1)]}]})
    test_id = created.json()["test"]["test_id"]
    result = (await client.get(f"/api/v1/tests/{test_id}/validation")).json()
    assert ("target_id", "REQUIRED") in {(i["field"], i["code"]) for i in result["issues"]}
    bad = await client.post("/api/v1/tests", json={"title": "T", "kind": "practice", "target_id": "1755000000000333", "duration_minutes": 5})
    assert bad.status_code == 422


async def test_per_section_timing_needs_a_limit_on_every_section(client, who, make_question):
    q1, q2 = await make_question(), await make_question(true_false())
    who.author()
    created = await client.post(
        "/api/v1/tests",
        json={
            "title": "T",
            "kind": "practice",
            "time_mode": "per_section",
            "sections": [
                {"title": "A", "time_limit_minutes": 10, "slots": [fixed(q1)]},
                {"title": "B", "slots": [fixed(q2)]},
            ],
        },
    )
    test_id = created.json()["test"]["test_id"]
    issues = (await client.get(f"/api/v1/tests/{test_id}/validation")).json()["issues"]
    assert [(i["field"], i["code"]) for i in issues] == [("sections[2].time_limit_minutes", "REQUIRED")]


async def test_a_retired_or_unapproved_question_cannot_be_used_and_a_used_one_cannot_be_retired(client, who, make_question, make_test):
    draft = await make_question(publish=False)
    who.author()
    created = await client.post("/api/v1/tests", json={"title": "T", "kind": "practice", "duration_minutes": 5, "sections": [{"title": "A", "slots": [fixed(draft)]}]})
    issues = (await client.get(f"/api/v1/tests/{created.json()['test']['test_id']}/validation")).json()["issues"]
    assert issues[0]["code"] == "QUESTION_UNAVAILABLE"

    live = await make_question()
    await make_test([fixed(live)])
    who.reviewer()
    refused = await client.post(f"/api/v1/questions/{live}/retire")
    assert refused.status_code == 409 and refused.json()["code"] == "QUESTION_IN_USE"


async def test_a_test_may_only_use_its_own_owners_questions(client, who, make_question):
    q1 = await make_question()
    who.employer_admin()
    created = await client.post("/api/v1/tests", json={"title": "Screen", "kind": "hiring", "duration_minutes": 5, "sections": [{"title": "A", "slots": [fixed(q1)]}]})
    assert created.status_code == 422 and created.json()["details"][0]["code"] == "QUESTION_NOT_FOUND"  # a platform question, not the employer's


async def test_employers_author_and_publish_only_hiring_tests_in_their_own_bank(client, who):
    who.recruiter()
    question = (await client.post("/api/v1/questions", json=mcq())).json()["question"]
    assert question["organization_id"] is not None
    wrong_kind = await client.post("/api/v1/tests", json={"title": "T", "kind": "final", "target_id": "1755000000000555", "duration_minutes": 5})
    assert wrong_kind.status_code == 422 and wrong_kind.json()["details"][0]["code"] == "HIRING_ONLY"

    await client.post(f"/api/v1/questions/{question['question_id']}/submit")
    who.employer_admin()
    assert (await client.post(f"/api/v1/questions/{question['question_id']}/approve", json={})).status_code == 200
    who.recruiter()
    test_id = (
        await client.post(
            "/api/v1/tests",
            json={"title": "Screen", "kind": "hiring", "duration_minutes": 15, "sections": [{"title": "A", "slots": [fixed(question["question_id"])]}]},
        )
    ).json()["test"]["test_id"]
    assert (await client.post(f"/api/v1/tests/{test_id}/submit")).status_code == 200
    assert (await client.post(f"/api/v1/tests/{test_id}/approve", json={})).status_code == 403  # a recruiter cannot approve
    who.employer_admin()
    assert (await client.post(f"/api/v1/tests/{test_id}/approve", json={})).status_code == 200


async def test_another_employer_cannot_see_a_hiring_test_or_question(client, who):
    who.recruiter()
    question_id = (await client.post("/api/v1/questions", json=mcq())).json()["question"]["question_id"]
    test_id = (await client.post("/api/v1/tests", json={"title": "Screen", "kind": "hiring", "duration_minutes": 15})).json()["test"]["test_id"]
    who.recruiter(user_id=1755000000007150, organization_id=1755000000007006)
    assert (await client.get(f"/api/v1/questions/{question_id}")).status_code == 404
    assert (await client.get(f"/api/v1/tests/{test_id}")).status_code == 404
    assert (await client.get("/api/v1/tests")).json()["page_context"]["total_records"] == 0


async def test_students_cannot_author_or_read_definitions(client, who, make_question, make_test):
    q1 = await make_question()
    test_id = await make_test([fixed(q1)])
    who.student()
    assert (await client.post("/api/v1/questions", json=mcq())).status_code == 403
    assert (await client.get(f"/api/v1/tests/{test_id}")).status_code == 404
    assert (await client.get(f"/api/v1/questions/{q1}")).status_code == 404
    assert (await client.get("/api/v1/questions")).status_code == 403
