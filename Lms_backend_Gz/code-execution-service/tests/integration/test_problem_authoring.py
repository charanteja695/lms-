import json

from httpx import AsyncClient

from tests.conftest import AUTHOR, STUDENT, ProblemFactory

V1 = "/api/v1"
HIDDEN_EXPECTED = "TOP-SECRET-EXPECTED-777"
HIDDEN_INPUT = "TOP-SECRET-INPUT-888"


async def test_only_authors_create_problems(client: AsyncClient, as_student, as_reviewer, as_author) -> None:
    body = {"title": "Sum of two numbers", "statement": "Print a + b."}
    as_student()
    assert (await client.post(f"{V1}/problems", json=body)).status_code == 403
    as_reviewer()  # reviewing is read-only
    assert (await client.post(f"{V1}/problems", json=body)).status_code == 403

    as_author()
    created = await client.post(f"{V1}/problems", json=body)
    assert created.status_code == 201
    problem = created.json()["problem"]
    assert (problem["status"], problem["test_case_count"], problem["created_by"]) == ("draft", 0, str(AUTHOR))
    assert (problem["difficulty"], problem["time_limit_ms"], problem["compare_mode"]) == ("easy", 2000, "trim")


async def test_a_problem_cannot_be_published_until_it_is_ready(client: AsyncClient, make_problem: ProblemFactory) -> None:
    problem_id = await make_problem(cases=[], publish=False)
    response = await client.post(f"{V1}/problems/{problem_id}/publish")
    assert response.status_code == 422
    assert response.json()["details"][0]["code"] == "NO_TEST_CASES"

    await client.post(f"{V1}/problems/{problem_id}/test-cases", json={"input": "1 2", "expected": "3"})
    assert (await client.post(f"{V1}/problems/{problem_id}/publish")).json()["problem"]["status"] == "published"


async def test_publishing_freezes_the_problem(client: AsyncClient, make_problem: ProblemFactory) -> None:
    problem_id = await make_problem()
    edit = await client.patch(f"{V1}/problems/{problem_id}", json={"title": "Changed"})
    assert (edit.status_code, edit.json()["code"]) == (400, "PROBLEM_NOT_DRAFT")
    assert (await client.post(f"{V1}/problems/{problem_id}/test-cases", json={"expected": "x"})).json()["code"] == "PROBLEM_NOT_DRAFT"
    assert (await client.delete(f"{V1}/problems/{problem_id}")).json()["code"] == "PROBLEM_NOT_DRAFT"
    assert (await client.post(f"{V1}/problems/{problem_id}/publish")).json()["code"] == "PROBLEM_NOT_DRAFT"

    retired = await client.post(f"{V1}/problems/{problem_id}/retire")
    assert retired.json()["problem"]["status"] == "retired"
    assert (await client.post(f"{V1}/problems/{problem_id}/retire")).json()["code"] == "PROBLEM_NOT_PUBLISHED"


async def test_a_draft_can_be_edited_and_deleted(client: AsyncClient, make_problem: ProblemFactory) -> None:
    problem_id = await make_problem(cases=[], publish=False)
    edited = await client.patch(
        f"{V1}/problems/{problem_id}",
        json={"title": "Better title", "difficulty": "hard", "tags": ["Arrays", "arrays", "math"], "time_limit_ms": 500},
    )
    problem = edited.json()["problem"]
    assert (problem["title"], problem["difficulty"], problem["time_limit_ms"]) == ("Better title", "hard", 500)
    assert problem["tags"] == ["arrays", "math"]  # lower-cased and de-duplicated

    assert (await client.delete(f"{V1}/problems/{problem_id}")).status_code == 204
    assert (await client.get(f"{V1}/problems/{problem_id}/author")).status_code == 404


async def test_students_see_published_problems_and_never_the_hidden_cases(client: AsyncClient, make_problem: ProblemFactory, as_student) -> None:
    published = await make_problem(
        cases=[
            {"input": "1 2\n", "expected": "3\n", "is_sample": True, "explanation": "1 + 2 = 3"},
            {"input": HIDDEN_INPUT, "expected": HIDDEN_EXPECTED},
        ]
    )
    draft = await make_problem(cases=[], publish=False, title="Unfinished draft")

    as_student()
    shown = await client.get(f"{V1}/problems/{published}")
    problem = shown.json()["problem"]
    assert problem["samples"] == [{"position": 1, "input": "1 2\n", "expected": "3\n", "explanation": "1 + 2 = 3"}]
    assert HIDDEN_EXPECTED not in shown.text and HIDDEN_INPUT not in shown.text  # not anywhere in the response
    assert "test_case_count" not in problem and "compare_mode" not in problem

    assert (await client.get(f"{V1}/problems/{draft}")).status_code == 404  # a draft does not exist for a student
    titles = [p["title"] for p in (await client.get(f"{V1}/problems")).json()["problems"]]
    assert titles == ["Sum of two numbers"]
    assert (await client.get(f"{V1}/problems/{draft}/author")).status_code == 403
    assert (await client.get(f"{V1}/problems/{published}/test-cases")).status_code == 403  # hidden cases are for staff


async def test_reviewers_see_drafts_and_everything_authors_do(client: AsyncClient, make_problem: ProblemFactory, as_reviewer) -> None:
    draft = await make_problem(cases=[{"input": HIDDEN_INPUT, "expected": HIDDEN_EXPECTED}], publish=False)
    as_reviewer()
    assert (await client.get(f"{V1}/problems", params={"status": "draft"})).json()["problems"][0]["status"] == "draft"
    author_view = (await client.get(f"{V1}/problems/{draft}/author")).json()["problem"]
    assert author_view["test_case_count"] == 1 and author_view["compare_mode"] == "trim"
    cases = (await client.get(f"{V1}/problems/{draft}/test-cases")).json()["test_cases"]
    assert (cases[0]["input"], cases[0]["expected"]) == (HIDDEN_INPUT, HIDDEN_EXPECTED)


async def test_listing_filters_and_paginates(client: AsyncClient, make_problem: ProblemFactory, as_student) -> None:
    await make_problem(title="Two sum", difficulty="easy", tags=["arrays"])
    await make_problem(title="Graph paths", difficulty="hard", tags=["graphs", "dfs"])
    await make_problem(title="Longest run", difficulty="medium", tags=["arrays", "dp"])
    as_student()

    async def get(params: dict) -> list[dict]:
        return (await client.get(f"{V1}/problems", params=params)).json()["problems"]

    assert sorted(p["title"] for p in await get({"difficulty": "hard"})) == ["Graph paths"]
    assert sorted(p["title"] for p in await get({"tag": "arrays"})) == ["Longest run", "Two sum"]
    assert sorted(p["title"] for p in await get({"search": "sum"})) == ["Two sum"]
    assert sorted(p["title"] for p in await get({"search": "%"})) == []  # wildcards are escaped, not interpreted
    page = (await client.get(f"{V1}/problems", params={"per_page": 2, "sort_order": "asc"})).json()
    assert [p["title"] for p in page["problems"]] == ["Two sum", "Graph paths"]
    assert page["page_context"]["total_records"] == 3 and page["page_context"]["has_more_page"] is True
    assert (await client.get(f"{V1}/problems", params={"per_page": 500})).status_code == 422


async def test_authoring_input_is_validated(client: AsyncClient, as_author) -> None:
    as_author()
    base = {"title": "Sum of two numbers", "statement": "Print a + b."}

    async def rejected(**extra: object) -> dict:
        response = await client.post(f"{V1}/problems", json={**base, **extra})
        assert response.status_code == 422, extra
        return response.json()

    assert (await rejected(time_limit_ms=999_999))["details"][0]["code"] == "TIME_LIMIT_TOO_HIGH"
    assert (await rejected(memory_limit_mb=99_999))["details"][0]["code"] == "MEMORY_LIMIT_TOO_HIGH"
    assert (await rejected(allowed_languages=["klingon"]))["details"][0]["code"] == "LANGUAGE_NOT_FOUND"
    assert (await rejected(allowed_languages=["sqlite"]))["details"][0]["code"] == "LANGUAGE_KIND_MISMATCH"
    assert (await rejected(setup_sql="CREATE TABLE t (x INT)"))["details"][0]["code"] == "SETUP_SQL_NOT_ALLOWED"
    assert (await rejected(compare_mode="rows_ordered"))["details"][0]["code"] == "COMPARE_MODE_MISMATCH"
    await rejected(title="ab")
    await rejected(tags=["bad!tag"])
    await rejected(problem_type="poetry")
    await rejected(unknown_field=1)


async def test_a_sql_problem_defaults_to_row_comparison(client: AsyncClient, as_author) -> None:
    as_author()
    created = await client.post(
        f"{V1}/problems",
        json={"title": "Top students", "statement": "List them.", "problem_type": "sql", "setup_sql": "CREATE TABLE s (x INT)", "allowed_languages": ["sqlite"]},
    )
    problem = created.json()["problem"]
    assert (problem["problem_type"], problem["compare_mode"], problem["has_setup_sql"]) == ("sql", "rows_unordered", True)
    assert "CREATE TABLE" not in created.text  # the setup script is never returned
    assert problem["allowed_languages"] == ["sqlite"]


async def test_allowed_languages_narrow_what_students_may_use(client: AsyncClient, make_problem: ProblemFactory, as_student) -> None:
    every = await make_problem(title="Any language")
    narrow = await make_problem(title="Python or JS only", allowed_languages=["python3", "javascript"])
    as_student()
    everything = (await client.get(f"{V1}/problems/{every}")).json()["problem"]["allowed_languages"]
    assert "python3" in everything and "java" in everything and "sqlite" not in everything  # programs only, for a code problem
    assert (await client.get(f"{V1}/problems/{narrow}")).json()["problem"]["allowed_languages"] == ["javascript", "python3"]


async def test_stats_are_for_staff(client: AsyncClient, make_problem: ProblemFactory, as_student, as_reviewer) -> None:
    problem_id = await make_problem()
    as_student(STUDENT)
    assert (await client.get(f"{V1}/problems/{problem_id}/stats")).status_code == 403
    as_reviewer()
    stats = (await client.get(f"{V1}/problems/{problem_id}/stats")).json()["stats"]
    assert stats == {"submissions": 0, "accepted": 0, "acceptance_percent": 0, "solvers": 0, "flagged": 0, "verdicts": {}}


async def test_problem_ids_that_are_not_ids_are_simply_not_found(client: AsyncClient, as_author) -> None:
    as_author()
    for path in ("/problems/abc", "/problems/0", "/problems/999", "/problems/abc/author"):
        assert (await client.get(f"{V1}{path}")).status_code == 404, path
    assert json.loads((await client.get(f"{V1}/problems/abc")).text)["code"] == "PROBLEM_NOT_FOUND"
