from datetime import timedelta

from sqlalchemy import select, update

from app.core.time import utcnow
from app.models.attempt import AttemptSection
from tests.conftest import MODULE, fixed, mcq, true_false


async def sectioned_test(make_question, make_test):
    q1, q2 = await make_question(mcq(correct="b")), await make_question(true_false(True))
    test_id = await make_test(
        [],
        kind="module",
        target_id=str(MODULE),
        time_mode="per_section",
        duration_minutes=None,
        sections=[
            {"title": "Quiz", "time_limit_minutes": 10, "slots": [fixed(q1, 5)]},
            {"title": "True or false", "time_limit_minutes": 10, "slots": [fixed(q2, 5)]},
        ],
    )
    return test_id, q1, q2


async def test_per_section_tests_reveal_and_lock_sections_in_order(client, who, enroll, make_question, make_test):
    test_id, q1, q2 = await sectioned_test(make_question, make_test)
    await enroll()
    who.student()
    started = (await client.post(f"/api/v1/tests/{test_id}/attempts", json={"start_now": True})).json()
    attempt_id = started["attempt"]["attempt_id"]
    assert [s["is_current"] for s in started["attempt"]["sections"]] == [True, False]
    assert started["attempt"]["remaining_seconds"] <= 20 * 60

    opened = (await client.post(f"/api/v1/attempts/{attempt_id}/resume")).json()
    assert [q["question_id"] for q in opened["questions"]] == [q1]  # the second section is not revealed yet
    early = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q2}", json={"response": {"value": True}, "revision": 1})
    assert early.status_code == 422 and early.json()["details"][0]["code"] == "SECTION_NOT_OPEN"

    assert (await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "b"}, "revision": 1})).status_code == 200
    finished = await client.post(f"/api/v1/attempts/{attempt_id}/finish-section")
    assert [s["is_current"] for s in finished.json()["attempt"]["sections"]] == [False, True]

    locked = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "a"}, "revision": 2})
    assert locked.status_code == 422 and locked.json()["details"][0]["code"] == "SECTION_CLOSED"
    assert (await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q2}", json={"response": {"value": True}, "revision": 1})).status_code == 200

    last = await client.post(f"/api/v1/attempts/{attempt_id}/finish-section")  # finishing the last section submits
    assert last.json()["attempt"]["status"] == "submitted"


async def test_a_section_whose_time_is_up_closes_and_the_next_one_opens(client, who, enroll, make_question, make_test, sessionmaker, redis):
    test_id, q1, q2 = await sectioned_test(make_question, make_test)
    await enroll()
    who.student()
    attempt_id = (await client.post(f"/api/v1/tests/{test_id}/attempts", json={"start_now": True})).json()["attempt"]["attempt_id"]
    async with sessionmaker() as db:  # the first section started 11 minutes ago
        first = (await db.execute(select(AttemptSection).where(AttemptSection.position == 1))).scalar_one()
        await db.execute(
            update(AttemptSection).where(AttemptSection.id == first.id).values(started_at=utcnow() - timedelta(minutes=11), deadline_at=utcnow() - timedelta(minutes=1))
        )
        await db.commit()
    await redis.delete(f"assessment:attempt:{attempt_id}:meta")

    closed = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1}", json={"response": {"selected": "b"}, "revision": 1})
    assert closed.status_code == 422 and closed.json()["details"][0]["code"] == "SECTION_CLOSED"
    state = (await client.get(f"/api/v1/attempts/{attempt_id}")).json()
    assert [s["is_current"] for s in state["attempt"]["sections"]] == [False, True]
    assert [q["question_id"] for q in state["questions"]] == [q1, q2]  # a finished section stays visible, read-only


async def test_response_bodies_never_shadow_the_envelope_code(app):
    """Every success response carries ``code: "SUCCESS"``; a resource field named ``code`` would silently replace it."""
    schema = app.openapi()
    offenders = []
    for name, model in schema["components"]["schemas"].items():
        properties = model.get("properties", {})
        if "status" in properties and "code" in properties and properties["code"].get("const") != "SUCCESS" and name != "ErrorResponse":
            offenders.append(name)
    assert offenders == []


async def test_every_operation_documents_its_errors(app):
    schema = app.openapi()
    for path, operations in schema["paths"].items():
        if path.startswith("/health"):
            continue
        for method, operation in operations.items():
            assert "summary" in operation, f"{method} {path} has no summary"
            if path != "/api/v1/tests/{test_id}/results/export" and not path.endswith("/export"):
                assert any(code in operation["responses"] for code in ("401", "403", "404", "422")), f"{method} {path} documents no errors"
