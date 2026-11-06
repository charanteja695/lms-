"""What only a real PostgreSQL can prove: the migration (up, down and up again, then checked for drift against the models), and
row locks under real concurrency — one winner when agents claim the same ticket, consecutive message numbers for simultaneous
replies, a single ticket for simultaneous retries of one idempotency key, and one breach flag per SLA sweep."""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.deps import _authenticate
from app.core.config import Settings, get_settings
from app.core.time import utcnow
from app.db.session import build_engine, build_sessionmaker
from app.main import create_app
from app.models import Base
from app.models.ticket import Ticket, TicketMessage
from app.services.ticket_service import sweep_sla
from tests.conftest import ORG_A, STAFF_A, STAFF_A2, STUDENT, _settings, make_claims, open_ticket

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres
API = "/api/v1"


@pytest.fixture(scope="module")
def pg_url(tmp_path_factory) -> Iterator[str]:
    pgserver = pytest.importorskip("pgserver")
    server = pgserver.get_server(tmp_path_factory.mktemp("pg_service"), cleanup_mode="delete")
    server.psql("CREATE DATABASE lms_support;")
    yield server.get_uri().rsplit("/", 1)[0].replace("postgresql://", "postgresql+asyncpg://", 1) + "/lms_support"
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
async def apps(settings, db_engine):
    import fakeredis.aioredis

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    sessionmaker = build_sessionmaker(db_engine)

    def build(user_id: int, role: str, org: int | None):
        app = create_app(settings)
        app.state.engine, app.state.sessionmaker, app.state.redis = db_engine, sessionmaker, redis
        app.dependency_overrides[get_settings] = lambda: settings
        claims = make_claims(user_id=user_id, role=role, organization_id=org, scopes=())
        app.dependency_overrides[_authenticate] = lambda: claims
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    yield build, sessionmaker
    await redis.aclose()


async def test_only_one_agent_wins_a_simultaneous_claim(apps):
    build, sessionmaker = apps
    async with build(STUDENT, "student", ORG_A) as student:
        ticket_id = (await open_ticket(student))["ticket_id"]
    clients = [build(uid, "staff", ORG_A) for uid in (STAFF_A, STAFF_A2, 1755000000030201, 1755000000030202, 1755000000030203)]
    responses = await asyncio.gather(*(c.post(f"{API}/agent/tickets/{ticket_id}/claim") for c in clients))
    for c in clients:
        await c.aclose()
    assert sorted(r.status_code for r in responses) == [200, 409, 409, 409, 409]
    async with sessionmaker() as db:
        ticket = (await db.execute(select(Ticket))).scalar_one()
        winner = next(r for r in responses if r.status_code == 200).json()["ticket"]["assignee_user_id"]
        assert str(ticket.assignee_user_id) == winner


async def test_simultaneous_replies_get_consecutive_numbers(apps):
    build, sessionmaker = apps
    async with build(STUDENT, "student", ORG_A) as student:
        ticket_id = (await open_ticket(student))["ticket_id"]
        replies = await asyncio.gather(*(student.post(f"{API}/tickets/{ticket_id}/replies", json={"body": f"message {n}"}) for n in range(8)))
    assert all(r.status_code == 201 for r in replies)
    async with sessionmaker() as db:
        numbers = sorted((await db.execute(select(TicketMessage.seq))).scalars())
    assert numbers == list(range(1, 10))


async def test_simultaneous_retries_of_one_key_open_one_ticket(apps):
    build, sessionmaker = apps
    async with build(STUDENT, "student", ORG_A) as student:
        responses = await asyncio.gather(*(student.post(f"{API}/tickets", json={"subject": "same request", "description": "x", "category": "technical"}, headers={"Idempotency-Key": "retry-key-0009"}) for _ in range(6)))
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count(Ticket.id)))).scalar_one() == 1
    assert all(r.status_code == 201 for r in responses) and len({r.json()["ticket"]["ticket_id"] for r in responses}) == 1


async def test_internal_retries_race_to_one_ticket(apps, internal_headers):
    build, sessionmaker = apps
    payload = {"requester_user_id": str(STUDENT), "organization_id": str(ORG_A), "subject": "Tutor hand-off", "description": "Summary."}
    async with build(STUDENT, "student", ORG_A) as client:
        responses = await asyncio.gather(*(client.post(f"{API}/internal/tickets", json=payload, headers={**internal_headers, "Idempotency-Key": "escalation-race-1"}) for _ in range(6)))
    assert all(r.status_code == 201 for r in responses)
    assert len({r.json()["ticket"]["ticket_id"] for r in responses}) == 1
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count(Ticket.id)))).scalar_one() == 1


async def test_concurrent_sweeps_flag_each_breach_once(apps, settings):
    build, sessionmaker = apps
    async with build(STUDENT, "student", ORG_A) as student:
        for _ in range(4):
            await open_ticket(student, category="technical")
    async with sessionmaker() as db:
        await db.execute(update(Ticket).values(first_response_due_at=utcnow() - timedelta(days=1), resolution_due_at=utcnow() - timedelta(days=1)))
        await db.commit()

    async def sweep() -> int:
        async with sessionmaker() as db:
            return await sweep_sla(db, settings)

    changed = await asyncio.gather(*(sweep() for _ in range(3)))
    assert sum(changed) == 8  # 4 tickets x (first response + resolution), however the sweeps interleaved
