"""Behaviour that only a real PostgreSQL can prove: the migration, JSONB, partial unique indexes, ``SKIP LOCKED``
claiming and row locks under real concurrency. SQLite (used by the rest of the suite) shares one connection across
all sessions, so it can check none of these."""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.db.session import build_engine
from app.models import Base
from app.models.attempt import Attempt, AttemptAnswer, CodingSubmission
from app.models.outbox_event import OutboxEvent
from app.services.grading_service import GradingService
from tests.conftest import COURSE, MODULE, _settings, fixed, mcq, pool, true_false

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def pg_url(tmp_path_factory) -> Iterator[str]:
    pgserver = pytest.importorskip("pgserver")
    server = pgserver.get_server(tmp_path_factory.mktemp("pg_service"), cleanup_mode="delete")
    server.psql("CREATE DATABASE lms_assessment;")
    yield server.get_uri().rsplit("/", 1)[0].replace("postgresql://", "postgresql+asyncpg://", 1) + "/lms_assessment"
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


async def take(client, who, test_id, answers, *, student=None):
    who.student(*([student] if student else []))
    attempt_id = (await client.post(f"/api/v1/tests/{test_id}/attempts", json={"start_now": True})).json()["attempt"]["attempt_id"]
    for question_id, response in answers.items():
        assert (await client.put(f"/api/v1/attempts/{attempt_id}/answers/{question_id}", json={"response": response, "revision": 1})).status_code == 200
    return attempt_id


async def test_the_whole_flow_runs_on_postgresql(client, who, enroll, make_question, make_test, work, sessionmaker):
    for n in range(6):
        await make_question(mcq(text=f"Pool question {n}", skills=["js"], tags=["a"]))
    q_tf = await make_question(true_false(True))
    test_id = await make_test(
        [fixed(q_tf, 2), pool(3, marks=2, skills=["js"], tags=["a"])], kind="module", target_id=str(MODULE), shuffle_options=True, pass_mark_percent=10
    )
    await enroll()
    who.student()
    attempt_id = (await client.post(f"/api/v1/tests/{test_id}/attempts", json={"start_now": True})).json()["attempt"]["attempt_id"]
    paper = (await client.post(f"/api/v1/attempts/{attempt_id}/resume")).json()["questions"]
    assert len(paper) == 4
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_tf}", json={"response": {"value": True}, "revision": 1})
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    await work.everything()
    result = (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]
    assert result["status"] == "graded" and result["score"] == 2 and result["result"] == "passed"
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count()).select_from(AttemptAnswer))).scalar_one() == 4  # one row per question, graded


async def test_two_simultaneous_prepares_for_one_student_end_up_with_one_attempt(client, who, enroll, make_question, make_test, sessionmaker):
    q1 = await make_question(mcq())
    test_id = await make_test([fixed(q1)], kind="module", target_id=str(MODULE))
    await enroll()
    who.student()
    responses = await asyncio.gather(*(client.post(f"/api/v1/tests/{test_id}/attempts", json={}) for _ in range(6)))
    assert {r.status_code for r in responses} == {201}
    assert len({r.json()["attempt"]["attempt_id"] for r in responses}) == 1  # the partial unique index arbitrates the race
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count()).select_from(Attempt))).scalar_one() == 1


async def test_submitting_twice_at_once_submits_once(client, who, enroll, make_question, make_test, sessionmaker):
    q1 = await make_question(mcq())
    test_id = await make_test([fixed(q1)], kind="module", target_id=str(MODULE))
    await enroll()
    attempt_id = await take(client, who, test_id, {q1: {"selected": "b"}})
    responses = await asyncio.gather(*(client.post(f"/api/v1/attempts/{attempt_id}/submit") for _ in range(5)))
    assert {r.status_code for r in responses} == {202}
    async with sessionmaker() as db:
        submitted = (await db.execute(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.event_type == "attempt.submitted"))).scalar_one()
    assert submitted == 1


async def test_concurrent_graders_never_take_the_same_attempt(client, who, enroll, make_question, make_test, sessionmaker, settings, redis):
    q1 = await make_question(mcq())
    test_id = await make_test([fixed(q1)], kind="module", target_id=str(MODULE), max_attempts=0)
    students = [1755000000007300 + n for n in range(12)]
    for n, student in enumerate(students):
        await enroll(student, enrollment_id=1755000000008300 + n)
        attempt_id = await take(client, who, test_id, {q1: {"selected": "b"}}, student=student)
        await client.post(f"/api/v1/attempts/{attempt_id}/submit")

    async def claim() -> list[int]:
        async with sessionmaker() as db:
            return await GradingService(db, settings, redis).claim(5)

    batches = await asyncio.gather(*(claim() for _ in range(4)))
    taken = [attempt for batch in batches for attempt in batch]
    assert len(taken) == len(set(taken)) == 12  # every attempt claimed by exactly one worker, none twice, none missed


async def test_grading_the_same_attempt_concurrently_produces_one_result(client, who, enroll, make_question, make_test, sessionmaker, settings, redis):
    q1 = await make_question(mcq())
    test_id = await make_test([fixed(q1)], kind="module", target_id=str(MODULE))
    await enroll()
    attempt_id = await take(client, who, test_id, {q1: {"selected": "b"}})
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")

    async def grade() -> None:
        async with sessionmaker() as db:
            await GradingService(db, settings, redis).grade_attempt(int(attempt_id))

    await asyncio.gather(*(grade() for _ in range(4)))  # a lease lapsing under a slow worker would look exactly like this
    async with sessionmaker() as db:
        counts = {
            event_type: (await db.execute(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.event_type == event_type))).scalar_one()
            for event_type in ("attempt.graded", "attempt.finalized")
        }
    assert counts == {"attempt.graded": 1, "attempt.finalized": 1}


async def test_concurrent_dispatchers_send_each_coding_answer_once(client, who, enroll, make_question, make_test, work, code_exec, sessionmaker):
    from tests.conftest import coding

    q_code = await make_question(coding(), default_marks=10)
    test_id = await make_test([fixed(q_code, 10)], kind="module", target_id=str(MODULE), max_attempts=0)
    for n in range(6):
        student = 1755000000007400 + n
        await enroll(student, enrollment_id=1755000000008400 + n)
        attempt_id = await take(client, who, test_id, {q_code: {"language": "python", "source": "print(1)"}}, student=student)
        await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    await work.flush()
    await work.grade()
    await asyncio.gather(*(work.dispatch() for _ in range(3)))
    assert len(code_exec.calls) == 6 and len({c["reference"] for c in code_exec.calls}) == 6
    async with sessionmaker() as db:
        statuses = set((await db.execute(select(CodingSubmission.status))).scalars())
    assert statuses == {"dispatched"}


async def test_final_test_pass_emits_course_passed_on_postgresql(client, who, enroll, make_question, make_test, work, send_event, sessionmaker):
    from datetime import timedelta

    from app.core.time import utcnow

    q1 = await make_question(mcq(correct="b"))
    test_id = await make_test([fixed(q1, 10)], kind="final", target_id=str(COURSE), proctoring_level="strict", requires_schedule=True)
    await enroll(eligible=True)
    who.exam_manager()
    await client.post(
        f"/api/v1/tests/{test_id}/schedules",
        json={"starts_at": (utcnow() - timedelta(minutes=1)).isoformat(), "ends_at": (utcnow() + timedelta(hours=1)).isoformat()},
    )
    attempt_id = await take(client, who, test_id, {q1: {"selected": "b"}})
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    await work.everything()
    await send_event("integrity.decided", {"attempt_id": attempt_id, "decision": "clear"})
    async with sessionmaker() as db:
        passed = (await db.execute(select(OutboxEvent.payload).where(OutboxEvent.event_type == "course.passed"))).scalars().all()
    assert len(passed) == 1 and passed[0]["percent"] == 100
