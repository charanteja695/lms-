import json
from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.core.config import get_settings
from app.core.time import utcnow
from app.engines.base import EngineError, ExecutionResult, Outcome
from app.models.outbox_event import OutboxEvent
from app.models.submission import Submission
from tests.conftest import ORG_A, STUDENT, STUDENT_2, SUM_SOLUTION, ProblemFactory

V1 = "/api/v1"
WRONG = "a, b = map(int, input().split())\nprint(a - b)\n"
CRASH = "print(int(input().split()[5]))\n"
LEAKY_CRASH = "import sys\nraise RuntimeError('the input was: ' + sys.stdin.read())\n"
SAMPLE_AND_HIDDEN = [
    {"input": "1 2\n", "expected": "3\n", "is_sample": True, "explanation": "1 + 2"},
    {"input": "10 20\n", "expected": "30\n"},
    {"input": "-5 5\n", "expected": "0\n"},
]


async def submit(client: AsyncClient, problem_id: int, source: str = SUM_SOLUTION, language: str = "python3", **kwargs: object) -> str:
    response = await client.post(f"{V1}/problems/{problem_id}/submissions", json={"language": language, "source": source}, **kwargs)
    assert response.status_code == 202, response.text
    return response.json()["submission"]["submission_id"]


async def verdict_of(client: AsyncClient, submission_id: str) -> dict:
    return (await client.get(f"{V1}/submissions/{submission_id}")).json()["submission"]


async def test_a_correct_solution_is_accepted_and_a_wrong_one_is_not(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, real_engine, drain
) -> None:
    problem_id = await make_problem(cases=SAMPLE_AND_HIDDEN)
    as_student()
    good = await submit(client, problem_id)
    queued = await verdict_of(client, good)
    assert (queued["status"], queued["verdict"], queued["results"]) == ("queued", None, [])

    bad = await submit(client, problem_id, WRONG)
    await drain(judge_with(real_engine))

    accepted = await verdict_of(client, good)
    assert (accepted["status"], accepted["verdict"], accepted["passed_count"], accepted["total_count"], accepted["score"]) == ("completed", "accepted", 3, 3, 100)
    assert accepted["judged_at"] and accepted["source"] == SUM_SOLUTION and accepted["compile_output"] is None
    assert [r["verdict"] for r in accepted["results"]] == ["accepted"] * 3

    rejected = await verdict_of(client, bad)
    assert (rejected["verdict"], rejected["passed_count"], rejected["score"]) == ("wrong_answer", 0, 0)  # a - b is never a + b here
    assert [r["verdict"] for r in rejected["results"]] == ["wrong_answer"] * 3


async def test_students_see_why_a_sample_failed_but_never_a_hidden_case(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, real_engine, drain
) -> None:
    problem_id = await make_problem(cases=SAMPLE_AND_HIDDEN)
    as_student()
    sid = await submit(client, problem_id, WRONG)
    await drain(judge_with(real_engine))
    response = await client.get(f"{V1}/submissions/{sid}")
    sample, hidden, _ = response.json()["submission"]["results"]

    assert (sample["is_sample"], sample["input"], sample["expected"], sample["actual"].strip()) == (True, "1 2\n", "3\n", "-1")
    assert (hidden["is_sample"], hidden["input"], hidden["expected"], hidden["actual"]) == (False, None, None, None)
    assert '"30' not in response.text and "10 20" not in response.text  # nothing of a hidden case is in the response


async def test_a_crash_message_is_shown_for_samples_and_withheld_for_hidden_cases(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, real_engine, drain
) -> None:
    problem_id = await make_problem(cases=SAMPLE_AND_HIDDEN)
    as_student()
    sid = await submit(client, problem_id, LEAKY_CRASH)  # an error message that quotes the input it read
    await drain(judge_with(real_engine))
    submission = await verdict_of(client, sid)
    sample, hidden, _ = submission["results"]
    assert submission["verdict"] == "runtime_error"
    assert "RuntimeError" in sample["message"]  # a sample's input is already public
    assert hidden["message"] is None and "10 20" not in json.dumps(submission)  # a hidden input must not leak through an error


async def test_the_score_is_weighted_and_the_verdict_is_the_first_failing_case(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, real_engine, drain
) -> None:
    problem_id = await make_problem(cases=[
        {"input": "1 1\n", "expected": "2\n", "weight": 1},
        {"input": "2 2\n", "expected": "999\n", "weight": 3},  # only a solution that prints 999 passes this one
        {"input": "3 3\n", "expected": "6\n", "weight": 1},
    ])
    as_student()
    sid = await submit(client, problem_id)
    await drain(judge_with(real_engine))
    submission = await verdict_of(client, sid)
    assert (submission["verdict"], submission["passed_count"], submission["total_count"]) == ("wrong_answer", 2, 3)
    assert submission["score"] == 40  # 2 of 5 weight points


async def test_runtime_errors_and_time_limits_are_verdicts(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, real_engine, drain
) -> None:
    problem_id = await make_problem(cases=[("1 2\n", "3\n")], time_limit_ms=100)
    as_student()
    crash = await submit(client, problem_id, CRASH)
    slow = await submit(client, problem_id, "import time\ntime.sleep(30)\n")
    await drain(judge_with(real_engine))
    assert (await verdict_of(client, crash))["verdict"] == "runtime_error"
    assert (await verdict_of(client, slow))["verdict"] == "time_limit_exceeded"


async def test_a_compile_error_is_reported_once_and_compiled_once(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, scripted_engine, drain
) -> None:
    problem_id = await make_problem(cases=SAMPLE_AND_HIDDEN)
    scripted_engine.behave = lambda request: ExecutionResult(Outcome.COMPILATION_ERROR, compile_output="main.cpp:3: error: expected ';'")
    as_student()
    sid = await submit(client, problem_id, "int main() { return 0 }", "cpp20")
    await drain(judge_with(scripted_engine))

    submission = await verdict_of(client, sid)
    assert (submission["verdict"], submission["passed_count"], submission["score"]) == ("compilation_error", 0, 0)
    assert submission["compile_output"] == "main.cpp:3: error: expected ';'"
    assert [r["verdict"] for r in submission["results"]] == ["compilation_error"] * 3
    assert len(scripted_engine.calls) == 1  # not once per test case
    assert [r["input"] for r in submission["results"]] == ["1 2\n", None, None]  # each case kept its own data


async def test_the_engine_is_given_the_problems_limits_scaled_for_the_language(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, scripted_engine, drain
) -> None:
    problem_id = await make_problem(cases=[("1", "1")], time_limit_ms=1_000, memory_limit_mb=128)
    as_student()
    await submit(client, problem_id, "class Main {}", "java")
    await submit(client, problem_id, "int main(){}", "c")
    await drain(judge_with(scripted_engine))
    java, c = sorted(scripted_engine.calls, key=lambda request: request.language.code == "c")
    assert (java.limits.cpu_time_s, java.limits.memory_mb, java.language.file_name) == (2.0, 256, "Main.java")  # java: 2x time, 2x memory
    assert (c.limits.cpu_time_s, c.limits.memory_mb, c.language.compiler_options) == (1.0, 128, "-std=c17 -O2")
    assert java.limits.wall_time_s > java.limits.cpu_time_s  # the wall clock always allows for start-up


async def test_compare_modes_decide_what_counts_as_a_match(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, scripted_engine, drain
) -> None:
    as_student()
    scripted_engine.behave = lambda request: ExecutionResult(Outcome.OK, stdout="  3.0000001   \n\n")
    lenient = await make_problem(cases=[("x", "3")], compare_mode="float", float_tolerance=1e-3)
    strict = await make_problem(cases=[("x", "3")], compare_mode="exact")
    per_case = await make_problem(cases=[{"input": "x", "expected": "3", "compare_mode": "float"}], compare_mode="exact")
    ids = {name: await submit(client, pid) for name, pid in (("lenient", lenient), ("strict", strict), ("per_case", per_case))}
    await drain(judge_with(scripted_engine))
    assert {name: (await verdict_of(client, sid))["verdict"] for name, sid in ids.items()} == {
        "lenient": "accepted", "strict": "wrong_answer", "per_case": "accepted",  # a case's own mode overrides the problem's
    }


async def test_only_allowed_languages_of_a_published_problem_can_be_used(client: AsyncClient, make_problem: ProblemFactory, as_student, as_author) -> None:
    narrow = await make_problem(allowed_languages=["python3"])
    as_student()
    for language in ("java", "sqlite", "klingon", "postgresql"):
        response = await client.post(f"{V1}/problems/{narrow}/submissions", json={"language": language, "source": "x"})
        assert (response.status_code, response.json()["details"][0]["code"]) == (422, "LANGUAGE_NOT_ALLOWED"), language
    assert "python3" in response.json()["details"][0]["message"]  # says what to use instead

    draft = await make_problem(cases=[], publish=False)
    as_student()
    assert (await client.post(f"{V1}/problems/{draft}/submissions", json={"language": "python3", "source": "x"})).status_code == 404
    assert (await client.post(f"{V1}/problems/999/submissions", json={"language": "python3", "source": "x"})).status_code == 404


async def test_a_retired_problem_takes_no_new_submissions_but_keeps_the_old_results(
    client: AsyncClient, make_problem: ProblemFactory, as_student, as_author, judge_with, real_engine, drain
) -> None:
    problem_id = await make_problem()
    as_student()
    sid = await submit(client, problem_id)
    await drain(judge_with(real_engine))

    as_author()
    await client.post(f"{V1}/problems/{problem_id}/retire")
    as_student()
    assert (await client.post(f"{V1}/problems/{problem_id}/submissions", json={"language": "python3", "source": SUM_SOLUTION})).status_code == 404
    assert (await verdict_of(client, sid))["verdict"] == "accepted"


async def test_submissions_are_private_and_listable(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, real_engine, drain
) -> None:
    first, second = await make_problem(title="First"), await make_problem(title="Second")
    as_student(STUDENT)
    mine = [await submit(client, first), await submit(client, first, WRONG), await submit(client, second)]
    as_student(STUDENT_2)
    theirs = await submit(client, first)
    await drain(judge_with(real_engine))

    assert (await client.get(f"{V1}/submissions/{mine[0]}")).status_code == 404  # someone else's looks like a missing one
    assert [s["submission_id"] for s in (await client.get(f"{V1}/submissions")).json()["submissions"]] == [theirs]

    as_student(STUDENT)
    listed = (await client.get(f"{V1}/submissions")).json()
    assert {s["submission_id"] for s in listed["submissions"]} == set(mine) and listed["page_context"]["total_records"] == 3
    only_first = (await client.get(f"{V1}/submissions", params={"problem_id": first})).json()["submissions"]
    assert len(only_first) == 2 and all(s["problem_id"] == str(first) for s in only_first)
    wrong = (await client.get(f"{V1}/submissions", params={"verdict": "wrong_answer"})).json()["submissions"]
    assert [s["submission_id"] for s in wrong] == [mine[1]]
    assert (await client.get(f"{V1}/submissions", params={"verdict": "nonsense"})).status_code == 422
    assert "source" not in listed["submissions"][0]  # the list is a summary; the source is on the detail


async def test_a_request_can_wait_for_the_verdict(client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, real_engine, drain) -> None:
    import asyncio

    problem_id = await make_problem()
    as_student()
    sid = await submit(client, problem_id)

    async def worker_soon() -> None:
        await asyncio.sleep(0.15)
        await drain(judge_with(real_engine))

    waited, _ = await asyncio.gather(client.get(f"{V1}/submissions/{sid}", params={"wait": 10}), worker_soon())
    body = waited.json()["submission"]
    assert (body["status"], body["verdict"], len(body["results"])) == ("completed", "accepted", 2)


async def test_solved_and_attempted_are_reported_for_the_caller(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, real_engine, drain
) -> None:
    solved, tried = await make_problem(title="Solved"), await make_problem(title="Tried")
    await make_problem(title="Untouched")
    as_student()
    await submit(client, solved)
    await submit(client, tried, WRONG)
    await drain(judge_with(real_engine))

    flags = {p["title"]: (p["solved"], p["attempted"]) for p in (await client.get(f"{V1}/problems")).json()["problems"]}
    assert flags == {"Solved": (True, True), "Tried": (False, True), "Untouched": (False, False)}
    assert (await client.get(f"{V1}/problems/{solved}")).json()["problem"]["solved"] is True
    assert [p["title"] for p in (await client.get(f"{V1}/problems", params={"solved": "true"})).json()["problems"]] == ["Solved"]
    assert sorted(p["title"] for p in (await client.get(f"{V1}/problems", params={"solved": "false"})).json()["problems"]) == ["Tried", "Untouched"]
    as_student(STUDENT_2)  # progress belongs to the person, not the problem
    assert {p["solved"] for p in (await client.get(f"{V1}/problems")).json()["problems"]} == {False}


async def test_submitting_is_idempotent_and_rate_limited(client: AsyncClient, app, settings, make_problem: ProblemFactory, as_student, sessionmaker) -> None:
    problem_id = await make_problem()
    limited = settings.model_copy(update={"RATE_LIMIT_ENABLED": True, "SUBMISSION_RATE_LIMIT_PER_USER_PER_MINUTE": 2})
    app.dependency_overrides[get_settings] = lambda: limited
    as_student()

    headers = {"Idempotency-Key": "submit-key-001"}
    first = await submit(client, problem_id, headers=headers)
    assert await submit(client, problem_id, headers=headers) == first  # a double click judges the code once
    assert (await client.post(f"{V1}/problems/{problem_id}/submissions", json={"language": "python3", "source": WRONG}, headers=headers)).json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count()).select_from(Submission))).scalar_one() == 1

    await submit(client, problem_id, WRONG)  # the second real submission this minute
    blocked = await client.post(f"{V1}/problems/{problem_id}/submissions", json={"language": "python3", "source": WRONG + "\n"})
    assert blocked.status_code == 429


async def test_students_cannot_choose_lane_reference_or_identity(client: AsyncClient, make_problem: ProblemFactory, as_student) -> None:
    problem_id = await make_problem()
    as_student()
    for extra in ({"priority": 2}, {"reference": "attempt:1"}, {"user_id": "1755000000001111"}, {"organization_id": "1"}):
        response = await client.post(f"{V1}/problems/{problem_id}/submissions", json={"language": "python3", "source": "x = 1", **extra})
        assert response.status_code == 422, extra


async def test_source_is_validated(client: AsyncClient, make_problem: ProblemFactory, as_student, settings) -> None:
    problem_id = await make_problem()
    as_student()
    assert (await client.post(f"{V1}/problems/{problem_id}/submissions", json={"language": "python3", "source": "  "})).json()["details"][0]["code"] == "REQUIRED"
    settings.MAX_SOURCE_BYTES = 1_024
    big = await client.post(f"{V1}/problems/{problem_id}/submissions", json={"language": "python3", "source": "x = 1\n" * 500})
    assert big.json()["details"][0]["code"] == "SOURCE_TOO_LARGE"


async def test_judging_publishes_submission_judged_with_everything_assessment_needs(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, real_engine, drain, sessionmaker
) -> None:
    problem_id = await make_problem(cases=SAMPLE_AND_HIDDEN)
    as_student()
    sid = await submit(client, problem_id, WRONG)
    await drain(judge_with(real_engine))

    async with sessionmaker() as db:
        [event] = (await db.execute(select(OutboxEvent))).scalars().all()
    assert (event.event_type, event.aggregate_type, event.published_at) == ("submission.judged", "submission", None)
    payload = event.payload
    assert payload["submission_id"] == sid and payload["problem_id"] == str(problem_id)
    assert (payload["user_id"], payload["organization_id"], payload["language"]) == (str(STUDENT), str(ORG_A), "python3")
    assert (payload["verdict"], payload["passed"], payload["total"], payload["score"]) == ("wrong_answer", 0, 3, 0)
    assert (payload["reference"], payload["flagged"]) == (None, False)


async def test_a_judged_submission_is_never_judged_or_announced_twice(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, scripted_engine, sessionmaker
) -> None:
    problem_id = await make_problem()
    as_student()
    await submit(client, problem_id)
    judge = judge_with(scripted_engine)
    async with sessionmaker() as db:
        submission_id = (await db.execute(select(Submission.id))).scalar_one()
    await judge.process_submission(submission_id)
    calls = len(scripted_engine.calls)
    await judge.process_submission(submission_id)  # e.g. a lapsed lease handed it to a second worker
    assert len(scripted_engine.calls) == calls
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count()).select_from(OutboxEvent))).scalar_one() == 1


async def test_an_engine_outage_is_retried_then_reported_as_an_internal_error_never_blamed_on_the_student(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, scripted_engine, drain, sessionmaker
) -> None:
    problem_id = await make_problem()
    as_student()
    sid = await submit(client, problem_id)
    scripted_engine.behave = lambda request: EngineError("judge0 unreachable")
    judge = judge_with(scripted_engine)

    await drain(judge)
    still_waiting = await verdict_of(client, sid)
    assert (still_waiting["status"], still_waiting["verdict"]) == ("queued", None)
    async with sessionmaker() as db:
        await db.execute(update(Submission).values(available_at=utcnow() - timedelta(seconds=1)))
        await db.commit()
    await drain(judge)

    final = await verdict_of(client, sid)
    assert (final["status"], final["verdict"], final["message"]) == ("completed", "internal_error", "judge0 unreachable")
    async with sessionmaker() as db:
        events = (await db.execute(select(OutboxEvent))).scalars().all()
    assert [e.payload["verdict"] for e in events] == ["internal_error"]  # assessment hears about it exactly once


async def test_a_submission_that_keeps_killing_workers_is_eventually_given_up_on(
    client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, scripted_engine, sessionmaker
) -> None:
    problem_id = await make_problem()
    as_student()
    sid = await submit(client, problem_id)
    async with sessionmaker() as db:  # three claims, each ending with the worker dying before it could record anything
        await db.execute(update(Submission).values(attempts=3, status="running"))
        await db.commit()
        submission_id = (await db.execute(select(Submission.id))).scalar_one()
    await judge_with(scripted_engine).process_submission(submission_id)
    final = await verdict_of(client, sid)
    assert (final["status"], final["verdict"]) == ("completed", "internal_error")
    assert scripted_engine.calls == []  # it was not run yet again
