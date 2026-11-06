"""A topic test needs at least 5 multiple-choice questions and 1 program; the final test 10 and 2 (both settings)."""

from tests.conftest import coding, fixed, mcq, pool

TOPIC = "1755000000000333"
COURSE = "1755000000000555"


def _rules_on(settings) -> None:
    settings.TOPIC_TEST_MIN_MCQ = 5
    settings.TOPIC_TEST_MIN_PROGRAMS = 1
    settings.FINAL_TEST_MIN_MCQ = 10
    settings.FINAL_TEST_MIN_PROGRAMS = 2


async def _draft(client, who, kind: str, target: str | None, slots: list[dict]) -> str:
    who.author()
    body = {"title": "Course test", "kind": kind, "duration_minutes": 20, "sections": [{"title": "Questions", "slots": slots}]}
    if target:
        body["target_id"] = target
    created = await client.post("/api/v1/tests", json=body)
    assert created.status_code == 201, created.text
    return created.json()["test"]["test_id"]


async def _validation(client, who, test_id: str) -> dict:
    who.author()
    return (await client.get(f"/api/v1/tests/{test_id}/validation")).json()


async def test_a_topic_test_reports_what_it_still_needs(client, who, make_question, settings):
    _rules_on(settings)
    questions = [await make_question(mcq(text=f"Question {n}")) for n in range(3)]
    test_id = await _draft(client, who, "topic", TOPIC, [fixed(q) for q in questions])

    result = await _validation(client, who, test_id)
    assert result["composition"] == {"multiple_choice": 3, "programs": 0, "required_multiple_choice": 5, "required_programs": 1}
    codes = {i["code"] for i in result["issues"]}
    assert {"TOO_FEW_MCQ", "TOO_FEW_PROGRAMS"} <= codes

    who.author()
    refused = await client.post(f"/api/v1/tests/{test_id}/submit")
    assert refused.status_code == 422


async def test_a_topic_test_with_five_mcq_and_a_program_is_complete(client, who, make_question, settings):
    _rules_on(settings)
    slots = [fixed(await make_question(mcq(text=f"Question {n}"))) for n in range(5)]
    slots.append(fixed(await make_question(coding())))
    test_id = await _draft(client, who, "topic", TOPIC, slots)

    result = await _validation(client, who, test_id)
    assert result["composition"]["multiple_choice"] == 5 and result["composition"]["programs"] == 1
    assert result["valid"] is True, result["issues"]


async def test_the_final_test_needs_two_programs(client, who, make_question, settings):
    _rules_on(settings)
    slots = [fixed(await make_question(mcq(text=f"Question {n}"))) for n in range(10)]
    slots.append(fixed(await make_question(coding())))
    test_id = await _draft(client, who, "final", COURSE, slots)

    result = await _validation(client, who, test_id)
    assert result["composition"]["required_programs"] == 2
    assert [i["code"] for i in result["issues"]] == ["TOO_FEW_PROGRAMS"]


async def test_a_pool_that_only_draws_multiple_choice_counts_as_multiple_choice(client, who, make_question, settings):
    _rules_on(settings)
    for n in range(5):
        await make_question(mcq(text=f"Pool question {n}"))
    test_id = await _draft(client, who, "topic", TOPIC, [pool(5, types=["mcq_single"])])
    result = await _validation(client, who, test_id)
    assert result["composition"]["multiple_choice"] == 5


async def test_a_practice_test_has_no_composition_rule(client, who, make_question, settings):
    _rules_on(settings)
    test_id = await _draft(client, who, "practice", None, [fixed(await make_question())])
    result = await _validation(client, who, test_id)
    assert result["composition"]["required_multiple_choice"] == 0
    assert not {i["code"] for i in result["issues"]} & {"TOO_FEW_MCQ", "TOO_FEW_PROGRAMS"}


async def test_a_builder_reads_every_topic_test_of_a_course_in_two_calls(client, who, make_question, settings):
    _rules_on(settings)
    first = await _draft(client, who, "topic", "1755000000000301", [fixed(await make_question(mcq(text="One")))])
    second = await _draft(client, who, "topic", "1755000000000302", [fixed(await make_question(coding()))])
    await _draft(client, who, "topic", "1755000000000399", [fixed(await make_question(mcq(text="Other course")))])

    who.author()
    listed = await client.get("/api/v1/tests", params={"kind": "topic", "target_ids": "1755000000000301,1755000000000302"})
    assert listed.status_code == 200, listed.text
    assert {t["test_id"] for t in listed.json()["tests"]} == {first, second}

    who.author()
    response = await client.post("/api/v1/tests/compositions", json={"test_ids": [first, second, first]})
    assert response.status_code == 200, response.text
    items = response.json()["compositions"]
    assert [i["test_id"] for i in items] == [first, second]
    assert (items[0]["multiple_choice"], items[0]["programs"]) == (1, 0)
    assert (items[1]["multiple_choice"], items[1]["programs"]) == (0, 1)
    assert items[0]["valid"] is False and items[0]["required_multiple_choice"] == 5


async def test_target_ids_must_be_a_list_of_ids(client, who):
    who.author()
    response = await client.get("/api/v1/tests", params={"target_ids": "12,abc"})
    assert response.status_code == 422
