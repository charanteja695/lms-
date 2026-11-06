import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.crypto import SecretCipher
from app.models.problem import Problem
from app.models.test_case import TestCase
from tests.conftest import ProblemFactory

V1 = "/api/v1"


def url(problem_id: int, suffix: str = "") -> str:
    return f"{V1}/problems/{problem_id}/test-cases{suffix}"


async def test_a_test_case_is_stored_encrypted_and_read_back_exactly(client: AsyncClient, make_problem: ProblemFactory, sessionmaker, cipher: SecretCipher) -> None:
    problem_id = await make_problem(cases=[], publish=False)
    exact_input = "line one  \n\tindented line\n\nlast line without newline"
    response = await client.post(url(problem_id), json={"input": exact_input, "expected": "42\n", "weight": 3, "is_sample": True})
    case = response.json()["test_case"]
    assert (case["input"], case["expected"], case["position"], case["weight"]) == (exact_input, "42\n", 1, 3)  # not trimmed

    async with sessionmaker() as db:
        row = (await db.execute(select(TestCase))).scalar_one()
    assert "line one" not in row.input_encrypted and "42" not in row.expected_encrypted  # unreadable in the database
    assert cipher.decrypt(row.input_encrypted) == exact_input and cipher.decrypt(row.expected_encrypted) == "42\n"


async def test_the_sql_setup_script_is_encrypted_too(client: AsyncClient, as_author, sessionmaker, cipher: SecretCipher) -> None:
    as_author()
    created = await client.post(
        f"{V1}/problems",
        json={"title": "Top students", "statement": "List them.", "problem_type": "sql", "setup_sql": "CREATE TABLE secret_schema (x INT)"},
    )
    assert created.status_code == 201
    async with sessionmaker() as db:
        stored = (await db.execute(select(Problem.setup_sql_encrypted))).scalar_one()
    assert "secret_schema" not in stored
    assert cipher.decrypt(stored) == "CREATE TABLE secret_schema (x INT)"


async def test_positions_follow_the_order_added_and_stay_contiguous(client: AsyncClient, make_problem: ProblemFactory) -> None:
    problem_id = await make_problem(cases=[("a", "1"), ("b", "2"), ("c", "3")], publish=False)
    cases = (await client.get(url(problem_id))).json()["test_cases"]
    assert [(c["position"], c["input"]) for c in cases] == [(1, "a"), (2, "b"), (3, "c")]

    await client.delete(url(problem_id, f"/{cases[0]['test_case_id']}"))
    after = (await client.get(url(problem_id))).json()["test_cases"]
    assert [(c["position"], c["input"]) for c in after] == [(1, "b"), (2, "c")]  # closed the gap


async def test_test_cases_can_be_reordered(client: AsyncClient, make_problem: ProblemFactory) -> None:
    problem_id = await make_problem(cases=[("a", "1"), ("b", "2"), ("c", "3")], publish=False)
    ids = [c["test_case_id"] for c in (await client.get(url(problem_id))).json()["test_cases"]]

    reordered = await client.post(url(problem_id, "/reorder"), json={"test_case_ids": [ids[2], ids[0], ids[1]]})
    assert [(c["position"], c["input"]) for c in reordered.json()["test_cases"]] == [(1, "c"), (2, "a"), (3, "b")]

    incomplete = await client.post(url(problem_id, "/reorder"), json={"test_case_ids": ids[:2]})
    assert (incomplete.status_code, incomplete.json()["details"][0]["code"]) == (422, "NOT_ALL_TEST_CASES")
    assert (await client.post(url(problem_id, "/reorder"), json={"test_case_ids": [ids[0], ids[0], ids[1]]})).status_code == 422


async def test_bulk_add_and_limits(client: AsyncClient, make_problem: ProblemFactory, settings) -> None:
    problem_id = await make_problem(cases=[], publish=False)
    bulk = await client.post(url(problem_id, "/bulk"), json={"test_cases": [{"input": str(n), "expected": str(n * 2)} for n in range(1, 6)]})
    assert bulk.status_code == 201 and [c["position"] for c in bulk.json()["test_cases"]] == [1, 2, 3, 4, 5]

    settings.MAX_TEST_CASES_PER_PROBLEM = 6
    over = await client.post(url(problem_id, "/bulk"), json={"test_cases": [{"expected": "x"}, {"expected": "y"}]})
    assert (over.status_code, over.json()["code"]) == (400, "TOO_MANY_TEST_CASES")
    assert len((await client.get(url(problem_id))).json()["test_cases"]) == 5  # all or nothing

    assert (await client.post(url(problem_id, "/bulk"), json={"test_cases": []})).status_code == 422


async def test_sample_and_size_limits(client: AsyncClient, make_problem: ProblemFactory, settings) -> None:
    problem_id = await make_problem(cases=[], publish=False)
    for n in range(10):
        assert (await client.post(url(problem_id), json={"expected": str(n), "is_sample": True})).status_code == 201
    too_many = await client.post(url(problem_id), json={"expected": "x", "is_sample": True})
    assert (too_many.status_code, too_many.json()["code"]) == (400, "TOO_MANY_SAMPLES")

    settings.MAX_TEST_CASE_BYTES = 1_024
    huge = await client.post(url(problem_id), json={"input": "x" * 2_000, "expected": "y"})
    assert (huge.status_code, huge.json()["details"][0]["code"]) == (422, "TOO_LARGE")
    assert (await client.post(url(problem_id), json={"input": "a\x00b", "expected": "y"})).status_code == 422  # NUL is refused


async def test_a_case_can_be_edited_while_the_problem_is_a_draft(client: AsyncClient, make_problem: ProblemFactory) -> None:
    problem_id = await make_problem(cases=[("1 2", "3")], publish=False)
    case_id = (await client.get(url(problem_id))).json()["test_cases"][0]["test_case_id"]

    edited = await client.patch(url(problem_id, f"/{case_id}"), json={"expected": "three", "weight": 5, "compare_mode": "token", "is_sample": True})
    case = edited.json()["test_case"]
    assert (case["input"], case["expected"], case["weight"], case["compare_mode"], case["is_sample"]) == ("1 2", "three", 5, "token", True)
    assert (await client.patch(url(problem_id, "/999"), json={"weight": 2})).status_code == 404

    await client.post(f"{V1}/problems/{problem_id}/publish")
    frozen = await client.patch(url(problem_id, f"/{case_id}"), json={"weight": 1})
    assert (frozen.status_code, frozen.json()["code"]) == (400, "PROBLEM_NOT_DRAFT")


@pytest.mark.parametrize(
    ("problem", "case", "code"),
    [
        ({"problem_type": "sql", "allowed_languages": ["sqlite"]}, {"expected": "x", "compare_mode": "trim"}, "COMPARE_MODE_MISMATCH"),
        ({}, {"expected": "x", "compare_mode": "rows_ordered"}, "COMPARE_MODE_MISMATCH"),
    ],
)
async def test_cases_must_suit_the_problem_type(client: AsyncClient, make_problem: ProblemFactory, problem: dict, case: dict, code: str) -> None:
    problem_id = await make_problem(cases=[], publish=False, **problem)
    response = await client.post(url(problem_id), json=case)
    assert (response.status_code, response.json()["details"][0]["code"]) == (422, code)


async def test_only_authors_write_and_only_staff_read(client: AsyncClient, make_problem: ProblemFactory, as_student, as_reviewer) -> None:
    problem_id = await make_problem(cases=[("1", "2")], publish=False)
    case_id = (await client.get(url(problem_id))).json()["test_cases"][0]["test_case_id"]

    as_student()
    for method, suffix in (("GET", ""), ("POST", ""), ("POST", "/bulk"), ("POST", "/reorder"), ("PATCH", f"/{case_id}"), ("DELETE", f"/{case_id}")):
        assert (await client.request(method, url(problem_id, suffix), json={})).status_code == 403, (method, suffix)

    as_reviewer()
    assert (await client.get(url(problem_id))).status_code == 200
    for method, suffix in (("POST", ""), ("PATCH", f"/{case_id}"), ("DELETE", f"/{case_id}")):
        assert (await client.request(method, url(problem_id, suffix), json={"expected": "x"})).status_code == 403, (method, suffix)
