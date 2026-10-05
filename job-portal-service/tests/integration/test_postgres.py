"""What only a real PostgreSQL can prove: the migration (up, down and up again, then checked for drift against the models), the JSON and
text queries the search uses, and behaviour under real concurrency — one application per student per job however many clicks, a work item
claimed by exactly one worker, an offer answered once, a rejection batch applied once."""

import asyncio
import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.deps import _authenticate, get_career, get_gateway
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.domain.enums import WorkKind
from app.main import create_app
from app.models import Base
from app.models.application import Application
from app.models.work import WorkItem
from app.services import work_service
from tests.conftest import API, RESUME, STUDENT, _settings, apply, hiring_world, make_claims

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def pg_url(tmp_path_factory) -> Iterator[str]:
    pgserver = pytest.importorskip("pgserver")
    server = pgserver.get_server(tmp_path_factory.mktemp("pg_service"), cleanup_mode="delete")
    server.psql("CREATE DATABASE lms_job_portal;")
    yield server.get_uri().rsplit("/", 1)[0].replace("postgresql://", "postgresql+asyncpg://", 1) + "/lms_job_portal"
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
    fastapi_app.dependency_overrides[get_career] = lambda: clients[1]
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


async def test_the_whole_hiring_flow_runs_on_postgresql(client, who, send_event, work, career, gateway):
    job_id = await hiring_world(client, who, send_event, work)
    application = await apply(client, who, job_id, career=career)
    aid = application["application_id"]
    await work()
    who.student()
    assert (await client.get(f"{API}/job-board?q=backend&location=chennai&skill=python&sort=relevance")).json()["jobs"][0]["job_id"] == job_id  # the JSON and LIKE queries
    assert (await client.get(f"{API}/recommendations")).json()["jobs"][0]["match"]["score"] > 0
    who.recruiter()
    listing = (await client.get(f"{API}/employer/jobs/{job_id}/applications?sort=screen&q=asha")).json()["applications"]
    assert listing[0]["screening"]["source"] == "ai" and listing[0]["candidate"]["name"] == "Asha Rao"
    await client.post(f"{API}/employer/applications/{aid}/advance")
    await client.post(f"{API}/employer/applications/{aid}/advance")
    assert (await client.post(f"{API}/employer/applications/{aid}/offer", json={"ctc": 900_000})).status_code == 201
    who.student()
    assert (await client.post(f"{API}/applications/{aid}/offer/respond", json={"accept": True})).status_code == 200
    who.recruiter()
    assert (await client.post(f"{API}/employer/applications/{aid}/place")).json()["application"]["status"] == "placed"
    who.staff()
    assert (await client.get(f"{API}/institution/summary")).json()["placed"] == 1
    assert gateway.completions


async def test_simultaneous_clicks_make_one_application(client, who, send_event, work, career, app, sessionmaker):
    job_id = await hiring_world(client, who, send_event, work)
    career.owners[RESUME] = STUDENT
    async with as_user(app, STUDENT, "student", 1755000000070001) as student:
        responses = await asyncio.gather(*(student.post(f"{API}/job-board/{job_id}/apply", json={"resume_id": str(RESUME)}) for _ in range(6)))
    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409, 409, 409] and {r.json().get("code") for r in responses if r.status_code == 409} == {"ALREADY_APPLIED"}
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count()).select_from(Application))).scalar_one() == 1
        assert (await db.execute(select(func.count()).select_from(WorkItem).where(WorkItem.kind == WorkKind.SCREEN))).scalar_one() == 1  # one screening, not six


async def test_a_work_item_is_claimed_by_exactly_one_worker(sessionmaker, settings):
    async with sessionmaker() as db:
        for n in range(12):
            await work_service.enqueue(db, WorkKind.MATCH_CANDIDATE, 1755000000078000 + n)
        await db.commit()

    async def claim() -> list[int]:
        async with sessionmaker() as db:
            return [item.ref_id for item in await work_service.claim(db, settings, limit=5)]

    taken = [ref for batch in await asyncio.gather(*(claim() for _ in range(6))) for ref in batch]
    assert len(taken) == len(set(taken)) == 12  # every item once, none twice


async def test_an_offer_is_answered_once(client, who, send_event, work, career, app):
    job_id = await hiring_world(client, who, send_event, work)
    application = await apply(client, who, job_id, career=career)
    aid = application["application_id"]
    await work()
    who.recruiter()
    await client.post(f"{API}/employer/applications/{aid}/advance")
    await client.post(f"{API}/employer/applications/{aid}/advance")
    await client.post(f"{API}/employer/applications/{aid}/offer", json={"ctc": 900_000})
    async with as_user(app, STUDENT, "student", 1755000000070001) as student:
        responses = await asyncio.gather(*(student.post(f"{API}/applications/{aid}/offer/respond", json={"accept": n % 2 == 0}) for n in range(6)))
    assert sorted(r.status_code for r in responses) == [200, 409, 409, 409, 409, 409]
    who.student()
    outcome = (await client.get(f"{API}/applications/{aid}")).json()["application"]
    winner = next(r for r in responses if r.status_code == 200).json()["offer"]["status"]
    assert outcome["status"] == ("offer_accepted" if winner == "accepted" else "offer_declined") and outcome["offer"]["status"] == winner


async def test_a_rejection_batch_is_applied_once(client, who, send_event, work, career, app, sessionmaker):
    job_id = await hiring_world(client, who, send_event, work)
    application = await apply(client, who, job_id, career=career)
    aid = application["application_id"]
    await work()
    async with as_user(app, 1755000000070111, "recruiter", 1755000000070011) as recruiter:
        body = {"application_ids": [aid], "reason": "Position filled", "confirm": True}
        responses = await asyncio.gather(*(recruiter.post(f"{API}/employer/jobs/{job_id}/applications/reject", json=body) for _ in range(5)))
    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409, 409]
    async with sessionmaker() as db:
        from app.models.application import RejectionBatch

        assert (await db.execute(select(func.count()).select_from(RejectionBatch))).scalar_one() == 1


async def test_redelivered_events_change_nothing(send_event, sessionmaker):
    event_id = uuid.uuid4().hex
    await send_event("course.published", {"course_id": "1755000000071001", "title": "Python"}, event_id=event_id)
    await send_event("course.published", {"course_id": "1755000000071001", "title": "Renamed"}, event_id=event_id)
    from app.models.refs import CourseRef

    async with sessionmaker() as db:
        assert (await db.get(CourseRef, 1755000000071001)).title == "Python"
