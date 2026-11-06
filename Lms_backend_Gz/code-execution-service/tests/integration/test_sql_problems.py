"""SQL problems end to end on the real SQLite engine: setup script, per-dataset hidden cases, row comparison."""

from httpx import AsyncClient

from tests.conftest import STUDENT, ProblemFactory

V1 = "/api/v1"
SETUP = """
CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT, marks INTEGER);
INSERT INTO students VALUES (1, 'Asha', 91), (2, 'Ravi', 78), (3, 'Meena', 85);
"""
SECRET_SEED = "INSERT INTO students VALUES (4, 'HiddenHelen', 99);"
TOP = "SELECT name FROM students WHERE marks >= 85"
CASES = [
    {"input": "", "expected": "name\nAsha\nMeena\n", "is_sample": True, "explanation": "the two above 85"},
    {"input": SECRET_SEED, "expected": "name\nAsha\nMeena\nHiddenHelen\n"},  # a hidden dataset: hard-coding cannot pass this
]


async def sql_problem(make_problem: ProblemFactory, **fields) -> int:
    return await make_problem(
        problem_type="sql", title="Students at or above 85", statement="List them.", setup_sql=SETUP,
        allowed_languages=["sqlite"], cases=fields.pop("cases", CASES), **fields,
    )


async def submit_query(client: AsyncClient, problem_id: int, query: str) -> str:
    response = await client.post(f"{V1}/problems/{problem_id}/submissions", json={"language": "sqlite", "source": query})
    assert response.status_code == 202, response.text
    return response.json()["submission"]["submission_id"]


async def test_a_correct_query_passes_every_dataset_and_a_hard_coded_answer_does_not(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, real_engine, drain
) -> None:
    problem_id = await sql_problem(make_problem)
    as_student()
    honest = await submit_query(client, problem_id, TOP)
    cheat = await submit_query(client, problem_id, "SELECT 'Asha' AS name UNION ALL SELECT 'Meena'")  # right for the visible sample only
    await drain(judge_with(real_engine))

    good = (await client.get(f"{V1}/submissions/{honest}")).json()["submission"]
    assert (good["verdict"], good["passed_count"], good["total_count"]) == ("accepted", 2, 2)
    bad = (await client.get(f"{V1}/submissions/{cheat}")).json()["submission"]
    assert (bad["verdict"], bad["passed_count"]) == ("wrong_answer", 1)
    assert [r["verdict"] for r in bad["results"]] == ["accepted", "wrong_answer"]


async def test_the_row_order_only_matters_when_the_problem_says_so(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, real_engine, drain
) -> None:
    unordered = await sql_problem(make_problem, cases=[{"expected": "name\nAsha\nMeena\n"}])
    ordered = await sql_problem(make_problem, compare_mode="rows_ordered", cases=[{"expected": "name\nAsha\nMeena\n"}])
    as_student()
    backwards = f"{TOP} ORDER BY name DESC"
    ids = {"unordered": await submit_query(client, unordered, backwards), "ordered": await submit_query(client, ordered, backwards)}
    await drain(judge_with(real_engine))
    assert {k: (await client.get(f"{V1}/submissions/{v}")).json()["submission"]["verdict"] for k, v in ids.items()} == {
        "unordered": "accepted", "ordered": "wrong_answer",
    }


async def test_a_broken_query_is_a_compile_error_with_the_databases_message(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, real_engine, drain
) -> None:
    problem_id = await sql_problem(make_problem)
    as_student()
    syntax = await submit_query(client, problem_id, "SELEC name FROM students")
    missing = await submit_query(client, problem_id, "SELECT name FROM teachers")
    await drain(judge_with(real_engine))
    for sid, fragment in ((syntax, "syntax error"), (missing, "no such table")):
        result = (await client.get(f"{V1}/submissions/{sid}")).json()["submission"]
        assert result["verdict"] == "compilation_error" and fragment in result["compile_output"]


async def test_students_see_the_sample_but_never_the_schema_script_or_hidden_data(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, real_engine, drain
) -> None:
    problem_id = await sql_problem(make_problem)
    as_student()
    shown = await client.get(f"{V1}/problems/{problem_id}")
    assert shown.json()["problem"]["samples"] == [{"position": 1, "input": "", "expected": "name\nAsha\nMeena\n", "explanation": "the two above 85"}]
    assert "CREATE TABLE" not in shown.text and "HiddenHelen" not in shown.text

    sid = await submit_query(client, problem_id, TOP + " AND 1 = 0")
    await drain(judge_with(real_engine))
    result = await client.get(f"{V1}/submissions/{sid}")
    assert "HiddenHelen" not in result.text and "INSERT INTO" not in result.text


async def test_a_student_can_try_a_query_against_the_problems_schema_before_submitting(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, real_engine, drain
) -> None:
    problem_id = await sql_problem(make_problem)
    as_student()
    with_schema = await client.post(f"{V1}/runs", json={"language": "sqlite", "source": "SELECT id, name FROM students ORDER BY id", "problem_id": str(problem_id)})
    without = await client.post(f"{V1}/runs", json={"language": "sqlite", "source": "SELECT id, name FROM students"})
    await drain(judge_with(real_engine))

    ran = (await client.get(f"{V1}/runs/{with_schema.json()['run']['run_id']}")).json()["run"]
    assert (ran["outcome"], ran["stdout"]) == ("ok", "id,name\n1,Asha\n2,Ravi\n3,Meena\n")
    empty = (await client.get(f"{V1}/runs/{without.json()['run']['run_id']}")).json()["run"]
    assert (empty["outcome"], "no such table" in empty["compile_output"]) == ("compilation_error", True)  # no schema without the problem


async def test_sql_runs_are_tied_to_a_visible_sql_problem(client: AsyncClient, make_problem: ProblemFactory, as_student) -> None:
    sql_id = await sql_problem(make_problem)
    code_id = await make_problem()
    draft = await sql_problem(make_problem, publish=False, cases=[])
    as_student(STUDENT)
    body = {"language": "sqlite", "source": "SELECT 1"}
    assert (await client.post(f"{V1}/runs", json={**body, "problem_id": str(code_id)})).json()["code"] == "RUN_PROBLEM_NOT_SQL"
    assert (await client.post(f"{V1}/runs", json={**body, "problem_id": str(draft)})).json()["code"] == "PROBLEM_NOT_FOUND"
    assert (await client.post(f"{V1}/runs", json={**body, "problem_id": str(sql_id)})).status_code == 202


async def test_a_sql_problem_only_accepts_sql_languages(client: AsyncClient, make_problem: ProblemFactory, as_student) -> None:
    problem_id = await sql_problem(make_problem)
    as_student()
    response = await client.post(f"{V1}/problems/{problem_id}/submissions", json={"language": "python3", "source": "print(1)"})
    assert (response.status_code, response.json()["details"][0]["code"]) == (422, "LANGUAGE_NOT_ALLOWED")
    shown = (await client.get(f"{V1}/problems/{problem_id}")).json()["problem"]
    assert shown["allowed_languages"] == ["sqlite"] and shown["problem_type"] == "sql"
