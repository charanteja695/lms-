"""Behaviour that only a real PostgreSQL can prove: the migration, SKIP LOCKED claiming, the idempotency-key race,
JSONB, and the fingerprint index. SQLite (used by the rest of the suite) cannot check any of these."""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.time import utcnow
from app.db.session import build_engine, build_sessionmaker
from app.domain.enums import JobStatus, Priority
from app.engines.base import ExecutionResult, Outcome
from app.main import create_app
from app.models import Base
from app.models.run import Run
from app.models.submission import Submission
from app.services.queue_service import QueueService
from app.worker.runner import run_job_loop
from tests.conftest import STUDENT, STUDENT_2, SUM_SOLUTION, ProblemFactory, _settings
from tests.integration.test_queue_and_worker import add_runs

ROOT = Path(__file__).resolve().parents[2]
V1 = "/api/v1"
pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def pg_url(tmp_path_factory) -> Iterator[str]:
    pgserver = pytest.importorskip("pgserver")
    server = pgserver.get_server(tmp_path_factory.mktemp("pg_service"), cleanup_mode="delete")
    server.psql("CREATE DATABASE lms_code_execution;")
    yield server.get_uri().rsplit("/", 1)[0].replace("postgresql://", "postgresql+asyncpg://", 1) + "/lms_code_execution"
    server.cleanup()


def alembic(pg_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", *args], cwd=ROOT, env={**os.environ, "DATABASE_URL": pg_url}, capture_output=True, text=True, check=False
    )


@pytest.fixture(scope="module")
def migrated(pg_url: str) -> str:
    """The schema comes from the real migration, not from create_all: what production runs is what is tested."""
    for step in (("upgrade", "head"), ("downgrade", "base"), ("upgrade", "head")):
        result = alembic(pg_url, *step)
        assert result.returncode == 0, f"alembic {' '.join(step)} failed:\n{result.stderr[-1500:]}"
    check = alembic(pg_url, "check")
    assert check.returncode == 0, f"the models and the migration disagree:\n{check.stdout[-800:]}{check.stderr[-800:]}"
    return pg_url


# The fixtures below shadow conftest's so every test in this module runs against PostgreSQL.


@pytest.fixture
def settings(migrated: str) -> Settings:
    return _settings(DATABASE_URL=migrated)


@pytest.fixture
async def db_engine(settings: Settings) -> AsyncIterator[AsyncEngine]:
    engine = build_engine(settings)
    async with engine.begin() as conn:
        tables = ", ".join(f'"{name}"' for name in Base.metadata.tables)
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))  # noqa: S608  (table names come from our own metadata)
    yield engine
    await engine.dispose()


@pytest.fixture
def sessionmaker(db_engine: AsyncEngine) -> async_sessionmaker:
    return build_sessionmaker(db_engine)


@pytest.fixture
async def app(db_engine: AsyncEngine, sessionmaker: async_sessionmaker, settings: Settings):
    fastapi_app = create_app(settings)
    fastapi_app.state.engine = db_engine
    fastapi_app.state.sessionmaker = sessionmaker
    fastapi_app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    yield fastapi_app
    await fastapi_app.state.redis.aclose()


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def test_the_migration_applies_reverses_and_matches_the_models(migrated: str) -> None:
    assert migrated  # the fixture asserted upgrade -> downgrade -> upgrade -> no drift


async def test_concurrent_workers_never_claim_the_same_job(sessionmaker, settings) -> None:
    async with sessionmaker() as db:
        db.add_all([Run(public_id=700_000 + n, user_id=1, language_code="python3", source="x", priority=Priority.PRACTICE) for n in range(60)])
        await db.commit()

    async def worker() -> list[int]:
        async with sessionmaker() as db:
            return [job.public_id for job in await QueueService(db, settings).claim(Run, 20)]

    a, b, c = await asyncio.gather(worker(), worker(), worker())
    claimed = a + b + c
    assert len(claimed) == 60 and len(set(claimed)) == 60  # three workers, sixty jobs, no job taken twice and none missed
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count()).select_from(Run).where(Run.status == JobStatus.RUNNING))).scalar_one() == 60


async def test_two_simultaneous_requests_with_one_idempotency_key_make_one_submission(
    client: AsyncClient, make_problem: ProblemFactory, as_student, sessionmaker
) -> None:
    problem_id = await make_problem()
    as_student()
    body = {"language": "python3", "source": SUM_SOLUTION}
    headers = {"Idempotency-Key": "race-key-0001"}
    responses = await asyncio.gather(*(client.post(f"{V1}/problems/{problem_id}/submissions", json=body, headers=headers) for _ in range(6)))

    assert {r.status_code for r in responses} == {202}
    assert len({r.json()["submission"]["submission_id"] for r in responses}) == 1  # they all got the same submission
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count()).select_from(Submission))).scalar_one() == 1  # and it was judged once


async def test_the_whole_flow_on_postgresql(
    client: AsyncClient, make_problem: ProblemFactory, as_student, as_reviewer, judge_with, real_engine, drain
) -> None:
    problem_id = await make_problem(title="Arrays warm-up", tags=["arrays", "math"], difficulty="medium", cases=[
        {"input": "1 2\n", "expected": "3\n", "is_sample": True}, {"input": "5 5\n", "expected": "10\n", "weight": 2},
    ])
    await make_problem(title="Graphs", tags=["graphs"])

    as_student(STUDENT)
    original = (await client.post(f"{V1}/problems/{problem_id}/submissions", json={"language": "python3", "source": SUM_SOLUTION})).json()["submission"]["submission_id"]
    as_student(STUDENT_2)
    copy = (await client.post(f"{V1}/problems/{problem_id}/submissions", json={"language": "python3", "source": "# mine\nx, y = map(int, input().split())\nprint(x + y)\n"})).json()["submission"]["submission_id"]
    await drain(judge_with(real_engine))

    as_student(STUDENT)
    judged = (await client.get(f"{V1}/submissions/{original}")).json()["submission"]
    assert (judged["verdict"], judged["score"], [r["verdict"] for r in judged["results"]]) == ("accepted", 100, ["accepted", "accepted"])
    listed = (await client.get(f"{V1}/problems", params={"tag": "arrays"})).json()["problems"]  # JSONB tags, filtered in SQL
    assert [(p["title"], p["solved"]) for p in listed] == [("Arrays warm-up", True)]
    assert [p["title"] for p in (await client.get(f"{V1}/problems", params={"solved": "false"})).json()["problems"]] == ["Graphs"]

    as_reviewer()
    flagged = (await client.get(f"{V1}/review/submissions", params={"flagged": "true"})).json()["submissions"]
    assert [(s["submission_id"], s["similarity_percent"], s["similar_to_submission_id"]) for s in flagged] == [(copy, 100, original)]
    stats = (await client.get(f"{V1}/problems/{problem_id}/stats")).json()["stats"]
    assert (stats["submissions"], stats["accepted"], stats["solvers"], stats["flagged"]) == (2, 2, 2, 1)

# The worker loop runs several jobs at once, each in its own session. SQLite tests share ONE connection between
# every session, which interleaves their transactions and makes concurrency tests flaky by construction; on
# PostgreSQL each session has its own connection, so these are the trustworthy versions of the worker tests.

async def test_the_worker_loop_drains_the_queue_and_stops_cleanly(sessionmaker, settings, judge_with, scripted_engine) -> None:
    await add_runs(sessionmaker, 12)
    scripted_engine.behave = lambda request: ExecutionResult(Outcome.OK, stdout="ok")
    judge = judge_with(scripted_engine)
    stop = asyncio.Event()
    slots = asyncio.Semaphore(4)
    task = asyncio.create_task(run_job_loop("run", Run, judge.process_run, sessionmaker, settings, slots, stop))

    for _ in range(200):
        await asyncio.sleep(0.02)
        async with sessionmaker() as db:
            if all(run.status == JobStatus.COMPLETED for run in (await db.execute(select(Run))).scalars()):
                break
    stop.set()
    await asyncio.wait_for(task, timeout=5)  # the loop notices the stop and returns
    async with sessionmaker() as db:
        runs = (await db.execute(select(Run))).scalars().all()
    assert len(runs) == 12 and all((run.status, run.outcome, run.stdout) == (JobStatus.COMPLETED, "ok", "ok") for run in runs)
    assert len(scripted_engine.calls) == 12  # each exactly once


async def test_executions_in_flight_never_exceed_the_workers_concurrency(sessionmaker, settings, judge_with, scripted_engine) -> None:
    await add_runs(sessionmaker, 10)
    in_flight = peak = 0

    class SlowEngine:
        async def execute(self, request):
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.05)
            in_flight -= 1
            return ExecutionResult(Outcome.OK)

    judge = judge_with(SlowEngine())
    stop, slots = asyncio.Event(), asyncio.Semaphore(3)
    task = asyncio.create_task(run_job_loop("run", Run, judge.process_run, sessionmaker, settings, slots, stop))
    for _ in range(300):
        await asyncio.sleep(0.02)
        async with sessionmaker() as db:
            if all(run.status == JobStatus.COMPLETED for run in (await db.execute(select(Run))).scalars()):
                break
    stop.set()
    await asyncio.wait_for(task, timeout=5)
    assert 1 < peak <= 3  # it did work in parallel, but never more than it was sized for


async def test_a_job_that_blows_up_does_not_stop_the_worker_and_is_retried_after_its_lease(sessionmaker, settings, judge_with) -> None:
    await add_runs(sessionmaker, 2)

    class Flaky:
        def __init__(self) -> None:
            self.calls = 0

        async def execute(self, request):
            self.calls += 1
            if self.calls == 1:
                raise ValueError("a bug, not an EngineError")  # unexpected: nothing catches it inside the judge
            return ExecutionResult(Outcome.OK, stdout="fine")

    engine = Flaky()
    judge = judge_with(engine)
    stop, slots = asyncio.Event(), asyncio.Semaphore(2)
    task = asyncio.create_task(run_job_loop("run", Run, judge.process_run, sessionmaker, settings, slots, stop))
    for _ in range(100):
        await asyncio.sleep(0.02)
        async with sessionmaker() as db:
            done = [run for run in (await db.execute(select(Run))).scalars() if run.status == JobStatus.COMPLETED]
        if done:
            break
    stop.set()
    await asyncio.wait_for(task, timeout=5)
    assert len(done) == 1  # the other one crashed, was logged, and the loop carried on and served its neighbour
    async with sessionmaker() as db:
        stuck = [run for run in (await db.execute(select(Run))).scalars() if run.status != JobStatus.COMPLETED]
    assert len(stuck) == 1 and stuck[0].status == JobStatus.RUNNING and stuck[0].available_at > utcnow()  # leased: retried when it lapses
