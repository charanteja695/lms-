from httpx import AsyncClient

from tests.conftest import STUDENT, STUDENT_2, ProblemFactory

V1 = "/api/v1"


def url(problem_id: int, language: str) -> str:
    return f"{V1}/problems/{problem_id}/code/{language}"


async def test_with_nothing_saved_the_editor_gets_the_starter_template(client: AsyncClient, make_problem: ProblemFactory, as_student) -> None:
    problem_id = await make_problem()
    as_student()
    code = (await client.get(url(problem_id, "java"))).json()["saved_code"]
    assert code["updated_at"] is None and code["language"] == "java"
    assert "public class Main" in code["source"]  # switching language switches the starting point


async def test_code_is_saved_per_problem_per_language_per_student(client: AsyncClient, make_problem: ProblemFactory, as_student) -> None:
    first, second = await make_problem(title="First"), await make_problem(title="Second")
    as_student(STUDENT)
    saved = await client.put(url(first, "python3"), json={"source": "print('work in progress')  \n\tindented"})
    assert saved.status_code == 200 and saved.json()["saved_code"]["updated_at"] is not None

    assert (await client.get(url(first, "python3"))).json()["saved_code"]["source"] == "print('work in progress')  \n\tindented"  # exactly as typed
    assert "Main" in (await client.get(url(first, "java"))).json()["saved_code"]["source"]  # another language: still the template
    assert (await client.get(url(second, "python3"))).json()["saved_code"]["updated_at"] is None  # another problem

    as_student(STUDENT_2)
    assert (await client.get(url(first, "python3"))).json()["saved_code"]["updated_at"] is None  # another student

    as_student(STUDENT)
    await client.put(url(first, "python3"), json={"source": "print('v2')"})
    assert (await client.get(url(first, "python3"))).json()["saved_code"]["source"] == "print('v2')"  # overwritten, not duplicated


async def test_an_empty_draft_can_be_saved_but_not_an_oversized_one(client: AsyncClient, make_problem: ProblemFactory, as_student, settings) -> None:
    problem_id = await make_problem()
    as_student()
    assert (await client.put(url(problem_id, "python3"), json={"source": ""})).status_code == 200  # clearing the editor is normal
    settings.MAX_SOURCE_BYTES = 1_024
    big = await client.put(url(problem_id, "python3"), json={"source": "x = 1\n" * 500})
    assert (big.status_code, big.json()["details"][0]["code"]) == (422, "SOURCE_TOO_LARGE")


async def test_saving_needs_a_visible_problem_and_an_enabled_language(client: AsyncClient, make_problem: ProblemFactory, as_student, as_author) -> None:
    draft = await make_problem(cases=[], publish=False)
    published = await make_problem()
    as_student()
    assert (await client.put(url(draft, "python3"), json={"source": "x"})).status_code == 404  # students cannot see drafts
    assert (await client.put(url(published, "klingon"), json={"source": "x"})).json()["code"] == "LANGUAGE_NOT_FOUND"
    assert (await client.put(url(published, "postgresql"), json={"source": "x"})).status_code == 404  # disabled
    assert (await client.get(url(999, "python3"))).status_code == 404

    as_author()
    assert (await client.put(url(draft, "python3"), json={"source": "x = 1"})).status_code == 200  # authors can try their own drafts
