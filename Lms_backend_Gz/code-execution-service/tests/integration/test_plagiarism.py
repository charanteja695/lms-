from httpx import AsyncClient
from sqlalchemy import select

from app.engines.base import ExecutionResult, Outcome
from app.models.outbox_event import OutboxEvent
from tests.conftest import STUDENT, STUDENT_2, SUM_SOLUTION, ProblemFactory

V1 = "/api/v1"
ORIGINAL = "a, b = map(int, input().split())\nprint(a + b)\n"
DISGUISED = "# my own work\nx, y = map(int, input().split())   # read both\nprint(x + y)\n"  # renamed, commented, same shape
DIFFERENT = "import sys\ntotal = 0\nfor token in sys.stdin.read().split():\n    total += int(token)\nprint(total)\n"


async def _judge_all(client, problem_id, submissions, judge_with, scripted_engine, drain, as_student):
    scripted_engine.behave = lambda request: ExecutionResult(Outcome.OK, stdout="3\n")  # every one is a correct answer
    ids = []
    for user, source in submissions:
        as_student(user)
        response = await client.post(f"{V1}/problems/{problem_id}/submissions", json={"language": "python3", "source": source})
        ids.append(response.json()["submission"]["submission_id"])
        await drain(judge_with(scripted_engine))  # judged in order, so "earlier" and "later" are well defined
    return ids


async def test_a_disguised_copy_of_someone_elses_solution_is_flagged_the_original_is_not(
    client: AsyncClient, make_problem: ProblemFactory, as_student, as_reviewer, judge_with, scripted_engine, drain
) -> None:
    problem_id = await make_problem(cases=[("1 2", "3")])
    original, copy, other = await _judge_all(
        client, problem_id, [(STUDENT, ORIGINAL), (STUDENT_2, DISGUISED), (STUDENT_2 + 1, DIFFERENT)], judge_with, scripted_engine, drain, as_student
    )

    as_reviewer()
    review = {sid: (await client.get(f"{V1}/review/submissions/{sid}")).json()["submission"] for sid in (original, copy, other)}
    assert (review[original]["flagged"], review[original]["similarity_percent"]) == (False, None)  # nothing earlier to copy
    assert (review[copy]["flagged"], review[copy]["similarity_percent"], review[copy]["similar_to_submission_id"]) == (True, 100, original)
    assert review[other]["flagged"] is False  # a genuinely different solution, though also correct

    flagged = (await client.get(f"{V1}/review/submissions", params={"flagged": "true"})).json()["submissions"]
    assert [s["submission_id"] for s in flagged] == [copy] and flagged[0]["similarity_percent"] == 100

    matches = (await client.get(f"{V1}/review/submissions/{copy}/similar")).json()["matches"]
    assert [(m["submission_id"], m["user_id"], m["similarity_percent"]) for m in matches] == [(original, str(STUDENT), 100)]
    assert (await client.get(f"{V1}/review/submissions/{other}/similar")).json()["matches"] == []


async def test_resubmitting_your_own_solution_is_not_copying(
    client: AsyncClient, make_problem: ProblemFactory, as_student, as_reviewer, judge_with, scripted_engine, drain
) -> None:
    problem_id = await make_problem(cases=[("1 2", "3")])
    _, again = await _judge_all(client, problem_id, [(STUDENT, ORIGINAL), (STUDENT, ORIGINAL)], judge_with, scripted_engine, drain, as_student)
    as_reviewer()
    assert (await client.get(f"{V1}/review/submissions/{again}")).json()["submission"]["flagged"] is False


async def test_copying_is_only_looked_for_within_the_same_problem(
    client: AsyncClient, make_problem: ProblemFactory, as_student, as_reviewer, judge_with, scripted_engine, drain
) -> None:
    first, second = await make_problem(cases=[("1 2", "3")], title="First"), await make_problem(cases=[("1 2", "3")], title="Second")
    await _judge_all(client, first, [(STUDENT, ORIGINAL)], judge_with, scripted_engine, drain, as_student)
    [same_code_elsewhere] = await _judge_all(client, second, [(STUDENT_2, DISGUISED)], judge_with, scripted_engine, drain, as_student)
    as_reviewer()
    assert (await client.get(f"{V1}/review/submissions/{same_code_elsewhere}")).json()["submission"]["flagged"] is False


async def test_a_program_too_short_to_judge_is_never_flagged(
    client: AsyncClient, make_problem: ProblemFactory, as_student, as_reviewer, judge_with, scripted_engine, drain
) -> None:
    problem_id = await make_problem(cases=[("1 2", "3")])
    _, second = await _judge_all(client, problem_id, [(STUDENT, "print(3)"), (STUDENT_2, "print(3)")], judge_with, scripted_engine, drain, as_student)
    as_reviewer()
    review = (await client.get(f"{V1}/review/submissions/{second}")).json()["submission"]
    assert (review["flagged"], review["similarity_percent"]) == (False, None)  # one-liners all look alike; that proves nothing


async def test_the_threshold_decides_what_is_flagged_but_the_percentage_is_always_recorded(
    client: AsyncClient, make_problem: ProblemFactory, as_student, as_reviewer, judge_with, scripted_engine, drain, settings
) -> None:
    settings.SIMILARITY_FLAG_PERCENT = 100
    partial = ORIGINAL + "print('done')\nprint('bye')\nprint('again')\n"  # shares most, not all, of the original
    problem_id = await make_problem(cases=[("1 2", "3")])
    _, later = await _judge_all(client, problem_id, [(STUDENT, partial + "x = 1\ny = 2\n"), (STUDENT_2, partial)], judge_with, scripted_engine, drain, as_student)
    as_reviewer()
    review = (await client.get(f"{V1}/review/submissions/{later}")).json()["submission"]
    assert review["similarity_percent"] is not None and review["similarity_percent"] >= 50
    assert review["flagged"] == (review["similarity_percent"] >= 100)


async def test_the_plagiarism_signal_is_shared_with_assessment_and_counted_in_the_stats(
    client: AsyncClient, make_problem: ProblemFactory, as_student, as_reviewer, judge_with, scripted_engine, drain, sessionmaker
) -> None:
    problem_id = await make_problem(cases=[("1 2", "3")])
    await _judge_all(client, problem_id, [(STUDENT, ORIGINAL), (STUDENT_2, DISGUISED)], judge_with, scripted_engine, drain, as_student)

    async with sessionmaker() as db:
        events = (await db.execute(select(OutboxEvent).order_by(OutboxEvent.created_at))).scalars().all()
    assert [(e.payload["flagged"], e.payload["similarity_percent"]) for e in events] == [(False, None), (True, 100)]
    # assessment-service's plagiarism report points a reviewer at the submission this one copies
    assert events[0].payload["similar_to_submission_id"] is None
    assert events[1].payload["similar_to_submission_id"] == events[0].payload["submission_id"]

    as_reviewer()
    stats = (await client.get(f"{V1}/problems/{problem_id}/stats")).json()["stats"]
    assert (stats["submissions"], stats["accepted"], stats["acceptance_percent"], stats["solvers"], stats["flagged"]) == (2, 2, 100, 2, 1)


async def test_only_staff_can_see_the_review_views(client: AsyncClient, make_problem: ProblemFactory, as_student, act_as, judge_with, scripted_engine, drain) -> None:
    problem_id = await make_problem(cases=[("1 2", "3")])
    [sid] = await _judge_all(client, problem_id, [(STUDENT, SUM_SOLUTION)], judge_with, scripted_engine, drain, as_student)
    as_student()
    for path in ("/review/submissions", f"/review/submissions/{sid}", f"/review/submissions/{sid}/similar"):
        assert (await client.get(f"{V1}{path}")).status_code == 403, path

    act_as(STUDENT + 500, role="admin", organization_id=None, scopes=("exams.manage",))  # exam managers review; they do not author
    assert (await client.get(f"{V1}/review/submissions")).status_code == 200
    assert (await client.post(f"{V1}/problems", json={"title": "abc", "statement": "x"})).status_code == 403
