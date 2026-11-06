"""What only a real PostgreSQL can prove: the migration (up, down and up again, then checked for drift against the models), and behaviour
under real concurrency — one worker claims a work item, two people answering at once produce one recorded turn, an evaluation is stored once."""

import asyncio
import json
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.deps import _authenticate, get_codeexec, get_gateway
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.domain.enums import WorkKind
from app.main import create_app
from app.models import Base
from app.models.interview import Evaluation, InterviewTurn
from app.services import work_service
from tests.conftest import API, STUDENT, _settings, create_published_plan, make_claims, round_body

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def pg_url(tmp_path_factory) -> Iterator[str]:
    pgserver = pytest.importorskip("pgserver")
    server = pgserver.get_server(tmp_path_factory.mktemp("pg_service"), cleanup_mode="delete")
    server.psql("CREATE DATABASE lms_interview;")
    yield server.get_uri().rsplit("/", 1)[0].replace("postgresql://", "postgresql+asyncpg://", 1) + "/lms_interview"
    server.cleanup()


def alembic(pg_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", *args], cwd=ROOT, env={**os.environ, "DATABASE_URL": pg_url}, capture_output=True, text=True, check=False
    )


@pytest.fixture(scope="module")
def migrated(pg_url: str) -> str:
    for step in (("upgrade", "head"), ("downgrade", "base"), ("upgrade", "head")):
        result = alembic(pg_url, *step)
        assert result.returncode == 0, f"alembic {' '.join(step)} failed:\n{result.stderr[-1500:]}"
    check = alembic(pg_url, "check")
    assert check.returncode == 0, f"the models and the migration disagree:\n{check.stdout[-800:]}{check.stderr[-800:]}"
    return pg_url


@pytest.fixture
def settings(migrated: str) -> Settings:
    return _settings(DATABASE_URL=migrated)


@pytest.fixture
async def db_engine(settings: Settings) -> AsyncIterator[AsyncEngine]:
    engine = build_engine(settings)
    async with engine.begin() as conn:
        tables = ", ".join(f'"{name}"' for name in Base.metadata.tables)
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))  # noqa: S608
    yield engine
    await engine.dispose()


@pytest.fixture
async def app(db_engine, settings, clients):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    fastapi_app = create_app(settings)
    fastapi_app.state.engine, fastapi_app.state.sessionmaker, fastapi_app.state.redis = db_engine, build_sessionmaker(db_engine), redis
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    fastapi_app.dependency_overrides[get_gateway] = lambda: clients[0]
    fastapi_app.dependency_overrides[get_codeexec] = lambda: clients[1]
    yield fastapi_app
    await redis.aclose()


@pytest.fixture
def sessionmaker(db_engine):
    return build_sessionmaker(db_engine)


def as_user(app, user_id: int, role: str, org: int | None, scopes: tuple[str, ...] = ()) -> AsyncClient:
    """A client whose requests carry one user's identity, independent of the others (needed to race two people)."""
    claims = make_claims(user_id=user_id, role=role, organization_id=org, scopes=scopes)
    app.dependency_overrides[_authenticate] = lambda: claims
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_a_work_item_is_claimed_by_exactly_one_worker(sessionmaker, settings):
    async with sessionmaker() as db:
        for n in range(12):
            await work_service.enqueue(db, WorkKind.CREATE_SCREENING, 1755000000099000 + n, {}, dedupe=False)
        await db.commit()

    async def claim() -> list[int]:
        async with sessionmaker() as db:
            return [item.ref_id for item in await work_service.claim(db, settings, limit=5)]

    taken = [ref for batch in await asyncio.gather(*(claim() for _ in range(6))) for ref in batch]
    assert len(taken) == len(set(taken)) == 12  # every item once, none twice


async def test_two_identical_submissions_at_once_produce_one_recorded_turn(client, who, app, sessionmaker, gateway):
    """A network retry can send the same answer twice at once (same Idempotency-Key). The interview row's lock serialises the two requests, so
    whichever runs second always sees the first one's turn already there and replays it instead of recording a duplicate — true under real
    concurrent connections, which is what this test needs PostgreSQL (not SQLite) to prove."""
    rounds = [round_body(type_="intro", minutes=5, questions=("Tell me about yourself.",)), round_body(type_="technical", minutes=5, questions=("Describe a project.",))]
    plan_id = await create_published_plan(client, who, kind="mock", rounds=rounds, duration_minutes=10)
    who.student()
    interview_id = (await client.post(f"{API}/student/interviews", json={"plan_id": plan_id})).json()["interview"]["interview_id"]
    consent = await client.get(f"{API}/student/interviews/{interview_id}/consent")
    await client.post(f"{API}/student/interviews/{interview_id}/consent", json={"version": consent.json()["consent"]["version"], "recording": False})
    await client.post(f"{API}/student/interviews/{interview_id}/start")
    gateway.reply_follow_up(None)  # no follow-up: the director moves to the next round, so the interview is still in progress after this answer
    headers = {"Idempotency-Key": "concurrent-retry-attempt-1"}

    async with as_user(app, STUDENT, "student", None) as a, as_user(app, STUDENT, "student", None) as b:
        responses = await asyncio.gather(
            a.post(f"{API}/student/interviews/{interview_id}/turns", json={"text": "My one and only answer to this question."}, headers=headers),
            b.post(f"{API}/student/interviews/{interview_id}/turns", json={"text": "My one and only answer to this question."}, headers=headers),
        )
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    assert responses[0].json()["turns"]["turn"]["seq"] == responses[1].json()["turns"]["turn"]["seq"]  # both got the same, single turn back

    async with sessionmaker() as db:
        answers = int((await db.execute(select(func.count()).select_from(InterviewTurn).where(InterviewTurn.speaker == "candidate"))).scalar_one())
        assert answers == 1


async def test_an_evaluation_is_stored_once_per_interview(client, who, app, sessionmaker, gateway, work):
    plan_id = await create_published_plan(client, who, kind="mock", rounds=[round_body(type_="intro", minutes=5, questions=("Tell me about yourself.",))], duration_minutes=10)
    who.student()
    interview_id = (await client.post(f"{API}/student/interviews", json={"plan_id": plan_id})).json()["interview"]["interview_id"]
    consent = await client.get(f"{API}/student/interviews/{interview_id}/consent")
    await client.post(f"{API}/student/interviews/{interview_id}/consent", json={"version": consent.json()["consent"]["version"], "recording": False})
    await client.post(f"{API}/student/interviews/{interview_id}/start")
    gateway.reply_follow_up(None)
    await client.post(f"{API}/student/interviews/{interview_id}/turns", json={"text": "An answer worth scoring for this interview."})
    gateway.reply(json.dumps({"rounds": [{"round": "intro_1", "scores": {"communication": {"score": 4, "evidence": [{"quote": "An answer worth scoring"}]}}}], "summary": "Fine."}))

    await work()
    async with sessionmaker() as db:
        count = int((await db.execute(select(func.count()).select_from(Evaluation))).scalar_one())
        assert count == 1
