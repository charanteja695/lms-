import asyncio
from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.core.time import utcnow
from app.engines.base import EngineError, ExecutionResult, Outcome
from app.models.run import Run
from tests.conftest import ORG_A, STUDENT, STUDENT_2

V1 = "/api/v1"


def run_body(source: str = "print('hi')", **extra: object) -> dict:
    return {"language": "python3", "source": source, **extra}


async def make_run(client: AsyncClient, **kwargs: object) -> str:
    response = await client.post(f"{V1}/runs", **kwargs)
    assert response.status_code == 202, response.text
    return response.json()["run"]["run_id"]


async def test_a_run_is_queued_then_completed_by_a_worker(client: AsyncClient, as_student, judge_with, real_engine, drain) -> None:
    as_student()
    created = await client.post(f"{V1}/runs", json=run_body("name = input()\nprint(f'hello {name}')", stdin="Asha\n"))
    assert created.status_code == 202
    run = created.json()["run"]
    assert (run["status"], run["outcome"], run["stdout"], run["language"]) == ("queued", None, None, "python3")

    await drain(judge_with(real_engine))
    done = (await client.get(f"{V1}/runs/{run['run_id']}")).json()["run"]
    assert (done["status"], done["outcome"], done["stdout"].strip(), done["exit_code"]) == ("completed", "ok", "hello Asha", 0)
    assert done["time_ms"] is not None and done["finished_at"] is not None


async def test_crashes_time_limits_and_compile_errors_are_reported_as_outcomes(
    client: AsyncClient, as_student, judge_with, real_engine, scripted_engine, drain
) -> None:
    as_student()
    crash = await make_run(client, json=run_body("raise KeyError('nope')"))
    forever = await make_run(client, json=run_body("while True:\n    pass"))
    await drain(judge_with(real_engine, RUN_WALL_TIME_SECONDS=0.4))  # python's time multiplier is 3
    result = {rid: (await client.get(f"{V1}/runs/{rid}")).json()["run"] for rid in (crash, forever)}
    assert result[crash]["outcome"] == "runtime_error" and "KeyError" in result[crash]["stderr"]
    assert result[forever]["outcome"] == "time_limit_exceeded"

    scripted_engine.behave = lambda request: ExecutionResult(Outcome.COMPILATION_ERROR, compile_output="main.c:1: error: expected ';'")
    bad = await make_run(client, json={"language": "c", "source": "int main() { return 0 }"})
    await drain(judge_with(scripted_engine))
    failed = (await client.get(f"{V1}/runs/{bad}")).json()["run"]
    assert (failed["outcome"], failed["compile_output"]) == ("compilation_error", "main.c:1: error: expected ';'")


async def test_the_engine_gets_the_language_the_limits_and_the_input(client: AsyncClient, as_student, judge_with, scripted_engine, drain) -> None:
    as_student()
    await make_run(client, json={"language": "java", "source": "class Main {}", "stdin": "5"})
    await drain(judge_with(scripted_engine))
    request = scripted_engine.calls[0]
    assert (request.language.code, request.language.file_name, request.stdin) == ("java", "Main.java", "5")
    assert request.limits.memory_mb == 512 and request.limits.wall_time_s == 20  # java: 2x memory and time (base 256 MB, 10 s)


async def test_output_is_clipped_to_the_configured_limit(client: AsyncClient, as_student, judge_with, scripted_engine, drain, settings) -> None:
    as_student()
    rid = await make_run(client, json=run_body())
    scripted_engine.behave = lambda request: ExecutionResult(Outcome.OK, stdout="x" * 5_000)
    await drain(judge_with(scripted_engine, MAX_OUTPUT_BYTES=1_024))
    stdout = (await client.get(f"{V1}/runs/{rid}")).json()["run"]["stdout"]
    assert len(stdout) <= 1_025 and stdout.endswith("…")


async def test_only_the_owner_can_read_a_run(client: AsyncClient, as_student) -> None:
    as_student(STUDENT)
    rid = await make_run(client, json=run_body())
    as_student(STUDENT_2)
    assert (await client.get(f"{V1}/runs/{rid}")).status_code == 404  # looks exactly like a missing run
    assert (await client.get(f"{V1}/runs/{rid}/stream")).status_code == 404
    for missing in ("999", "abc"):
        assert (await client.get(f"{V1}/runs/{missing}")).json()["code"] == "RUN_NOT_FOUND"


async def test_bad_runs_are_refused_before_anything_is_queued(client: AsyncClient, as_student, sessionmaker, settings) -> None:
    as_student()
    assert (await client.post(f"{V1}/runs", json={"language": "klingon", "source": "x"})).json()["code"] == "LANGUAGE_NOT_FOUND"
    assert (await client.post(f"{V1}/runs", json={"language": "postgresql", "source": "select 1"})).status_code == 404  # disabled
    assert (await client.post(f"{V1}/runs", json=run_body("   \n"))).json()["details"][0]["code"] == "REQUIRED"

    settings.MAX_SOURCE_BYTES = 1_024
    settings.MAX_STDIN_BYTES = 10
    big = await client.post(f"{V1}/runs", json=run_body("x = 1\n" * 500))
    assert big.json()["details"][0]["code"] == "SOURCE_TOO_LARGE"
    assert (await client.post(f"{V1}/runs", json=run_body(stdin="x" * 11))).json()["details"][0]["code"] == "STDIN_TOO_LARGE"
    assert (await client.post(f"{V1}/runs", json=run_body(problem_id="1755000000009999"))).json()["code"] == "RUN_PROBLEM_NOT_SQL"
    assert (await client.post(f"{V1}/runs", json={"source": "x"})).status_code == 422
    assert (await client.post(f"{V1}/runs", json=run_body(unknown=1))).status_code == 422

    async with sessionmaker() as db:
        assert (await db.execute(select(func.count()).select_from(Run))).scalar_one() == 0


async def test_a_retried_create_returns_the_same_run(client: AsyncClient, as_student, sessionmaker) -> None:
    as_student()
    headers = {"Idempotency-Key": "retry-key-0001"}
    first = await make_run(client, json=run_body("print(1)"), headers=headers)
    again = await make_run(client, json=run_body("print(1)"), headers=headers)  # e.g. a double click or a network retry
    assert first == again
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count()).select_from(Run))).scalar_one() == 1

    reused = await client.post(f"{V1}/runs", json=run_body("print(2)"), headers=headers)  # same key, different code
    assert (reused.status_code, reused.json()["code"]) == (409, "IDEMPOTENCY_KEY_REUSED")

    as_student(STUDENT_2)
    other = await make_run(client, json=run_body("print(1)"), headers=headers)  # keys are per user
    assert other != first
    assert (await client.post(f"{V1}/runs", json=run_body(), headers={"Idempotency-Key": "short"})).status_code == 422


async def test_runs_are_rate_limited_per_user_and_per_institution(client: AsyncClient, app, settings, as_student) -> None:
    limited = settings.model_copy(update={"RATE_LIMIT_ENABLED": True, "RUN_RATE_LIMIT_PER_USER_PER_MINUTE": 3, "RUN_RATE_LIMIT_PER_ORG_PER_MINUTE": 5})
    from app.core.config import get_settings

    app.dependency_overrides[get_settings] = lambda: limited

    as_student(STUDENT)
    for n in range(3):
        assert (await client.post(f"{V1}/runs", json=run_body(f"print({n})"))).status_code == 202
    blocked = await client.post(f"{V1}/runs", json=run_body("print(99)"))
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) >= 1

    # A retry of an accepted request is not a new run, so it never counts against the limit.
    as_student(STUDENT_2)
    assert (await client.post(f"{V1}/runs", json=run_body("print(1)"), headers={"Idempotency-Key": "budget-key-1"})).status_code == 202
    assert (await client.post(f"{V1}/runs", json=run_body("print(1)"), headers={"Idempotency-Key": "budget-key-1"})).status_code == 202
    assert (await client.post(f"{V1}/runs", json=run_body("print(2)"))).status_code == 202  # org total is now 5 of 5
    over_org = await client.post(f"{V1}/runs", json=run_body("print(3)"))
    assert over_org.status_code == 429  # this user has budget left, but their institution does not

    as_student(STUDENT, organization_id=ORG_A + 1)  # a different institution is unaffected by the first one's burst
    assert (await client.post(f"{V1}/runs", json=run_body("print(0)"))).status_code == 429  # ...but this user is still over their own limit
    as_student(STUDENT_2 + 10, organization_id=ORG_A + 1)
    assert (await client.post(f"{V1}/runs", json=run_body("print(0)"))).status_code == 202


async def test_a_request_can_wait_for_the_result_instead_of_polling(client: AsyncClient, as_student, judge_with, real_engine, drain) -> None:
    as_student()
    rid = await make_run(client, json=run_body("print('done')"))

    async def worker_soon() -> None:
        await asyncio.sleep(0.15)
        await drain(judge_with(real_engine))

    waited, _ = await asyncio.gather(client.get(f"{V1}/runs/{rid}", params={"wait": 10}), worker_soon())
    assert waited.json()["run"]["status"] == "completed"
    assert waited.json()["run"]["stdout"].strip() == "done"

    never = await make_run(client, json=run_body("print('later')"))
    quick = await client.get(f"{V1}/runs/{never}", params={"wait": 0.1})  # gives up waiting, returns the current state
    assert quick.json()["run"]["status"] == "queued"
    assert (await client.get(f"{V1}/runs/{rid}", params={"wait": 999})).status_code == 422


async def test_progress_can_be_streamed_as_server_sent_events(client: AsyncClient, as_student, judge_with, real_engine, drain) -> None:
    as_student()
    rid = await make_run(client, json=run_body("print('streamed')"))

    async def worker_soon() -> None:
        await asyncio.sleep(0.15)
        await drain(judge_with(real_engine))

    streamed, _ = await asyncio.gather(client.get(f"{V1}/runs/{rid}/stream"), worker_soon())
    assert streamed.headers["content-type"].startswith("text/event-stream")
    events = [block for block in streamed.text.split("\n\n") if block]
    assert events[0].startswith("event: status") and '"status":"queued"' in events[0]
    assert events[-1].startswith("event: done") and '"outcome":"ok"' in events[-1] and "streamed" in events[-1]


async def test_a_run_is_never_executed_twice(client: AsyncClient, as_student, judge_with, scripted_engine, sessionmaker) -> None:
    as_student()
    await make_run(client, json=run_body())
    judge = judge_with(scripted_engine)
    async with sessionmaker() as db:
        run_id = (await db.execute(select(Run.id))).scalar_one()
    await judge.process_run(run_id)
    await judge.process_run(run_id)  # a duplicate claim (e.g. a lapsed lease) finds it already done
    assert len(scripted_engine.calls) == 1


async def test_an_engine_failure_is_retried_later_then_given_up_as_internal_error(
    client: AsyncClient, as_student, judge_with, scripted_engine, drain, sessionmaker
) -> None:
    as_student()
    rid = await make_run(client, json=run_body())
    scripted_engine.behave = lambda request: EngineError("judge0 is down")
    judge = judge_with(scripted_engine)  # JOB_MAX_ATTEMPTS is 2 in tests

    await drain(judge)
    state = (await client.get(f"{V1}/runs/{rid}")).json()["run"]
    assert state["status"] == "queued" and state["outcome"] is None  # the student sees no failure yet
    async with sessionmaker() as db:
        run = (await db.execute(select(Run))).scalar_one()
        assert run.attempts == 1 and run.available_at > utcnow()  # backing off, not hammering the engine
        await db.execute(update(Run).values(available_at=utcnow() - timedelta(seconds=1)))
        await db.commit()

    await drain(judge)
    final = (await client.get(f"{V1}/runs/{rid}")).json()["run"]
    assert (final["status"], final["outcome"], final["message"]) == ("completed", "internal_error", "judge0 is down")
    assert len(scripted_engine.calls) == 2


async def test_an_engine_that_recovers_gives_a_normal_result(client: AsyncClient, as_student, judge_with, scripted_engine, drain, sessionmaker) -> None:
    as_student()
    rid = await make_run(client, json=run_body())
    outcomes = iter([EngineError("blip"), ExecutionResult(Outcome.OK, stdout="fine")])
    scripted_engine.behave = lambda request: next(outcomes)
    judge = judge_with(scripted_engine)

    await drain(judge)
    async with sessionmaker() as db:
        await db.execute(update(Run).values(available_at=utcnow() - timedelta(seconds=1)))
        await db.commit()
    await drain(judge)
    assert (await client.get(f"{V1}/runs/{rid}")).json()["run"]["stdout"] == "fine"
