"""What only a real PostgreSQL can prove: the migration (up, down and up again, then checked for drift against the models), and
behaviour under real concurrency — a stale-edit race has exactly one winner, simultaneous version saves are numbered without gaps,
and duplicate certificate events leave one certificate on the profile."""

import asyncio
import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from lms_common.events import Event
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.deps import _authenticate
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.events.consumers.router import dispatch
from app.main import create_app
from app.models import Base
from app.models.profile import ProfileItem
from app.models.resume import ResumeVersion
from tests.conftest import (
    STUDENT,
    _settings,
    attempt_payload,
    certificate_payload,
    fill_profile,
    make_claims,
    seed_student,
)

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres
API = "/api/v1"


@pytest.fixture(scope="module")
def pg_url(tmp_path_factory) -> Iterator[str]:
    pgserver = pytest.importorskip("pgserver")
    server = pgserver.get_server(tmp_path_factory.mktemp("pg_service"), cleanup_mode="delete")
    server.psql("CREATE DATABASE lms_career;")
    yield server.get_uri().rsplit("/", 1)[0].replace("postgresql://", "postgresql+asyncpg://", 1) + "/lms_career"
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
async def student(settings, db_engine):
    """A client acting as the student, over the real database."""
    import fakeredis.aioredis

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app = create_app(settings)
    app.state.engine, app.state.sessionmaker, app.state.redis = db_engine, build_sessionmaker(db_engine), redis
    app.dependency_overrides[get_settings] = lambda: settings
    claims = make_claims(user_id=STUDENT, role="student", organization_id=1755000000050001, scopes=())
    app.dependency_overrides[_authenticate] = lambda: claims
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    await redis.aclose()


async def deliver(sessionmaker, settings, event_type: str, payload: dict, event_id: str | None = None) -> None:
    event = Event(event_id=event_id or uuid.uuid4().hex, event_type=event_type, aggregate_type="x", occurred_time=datetime.now(UTC), payload=payload)
    async with sessionmaker() as db:
        await dispatch(db, event, settings)
        await db.commit()


async def test_the_whole_flow_runs_on_postgresql(student, db_engine, settings):
    sessionmaker = build_sessionmaker(db_engine)

    async def send(event_type, payload):
        await deliver(sessionmaker, settings, event_type, payload)

    await seed_student(send)
    await send("certificate.issued", certificate_payload())
    await send("attempt.finalized", attempt_payload(1, percent=91.5))
    await fill_profile(student)
    resume = (await student.post(f"{API}/resumes", json={"title": "Backend Developer"})).json()["resume"]["resume_id"]
    detail = (await student.get(f"{API}/resumes/{resume}")).json()
    kinds = {s["key"] for s in detail["document"]["sections"]}
    assert {"education", "experience", "certificates", "skill_scores"} <= kinds and detail["ats"]["score"] > 0
    assert (await student.post(f"{API}/resumes/{resume}/versions", json={})).status_code == 201
    pdf = await student.get(f"{API}/resumes/{resume}/export/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    share = (await student.post(f"{API}/resumes/{resume}/share", json={"version_no": 1})).json()["share"]
    assert (await student.get(share["url_path"])).status_code == 200


async def test_a_stale_edit_race_has_exactly_one_winner(student):
    resume = (await student.post(f"{API}/resumes", json={"title": "Race", "blank": True})).json()["resume"]["resume_id"]
    responses = await asyncio.gather(*(student.patch(f"{API}/resumes/{resume}", json={"expected_revision": 0, "title": f"Title {n}"}) for n in range(6)))
    assert sorted(r.status_code for r in responses) == [200, 409, 409, 409, 409, 409]
    final = (await student.get(f"{API}/resumes/{resume}")).json()["resume"]
    winner = next(r for r in responses if r.status_code == 200).json()["resume"]["title"]
    assert final["draft_revision"] == 1 and final["title"] == winner


async def test_simultaneous_version_saves_are_numbered_without_gaps(student, db_engine):
    resume = (await student.post(f"{API}/resumes", json={"title": "Versions", "blank": True})).json()["resume"]["resume_id"]
    responses = await asyncio.gather(*(student.post(f"{API}/resumes/{resume}/versions", json={"label": f"v{n}"}) for n in range(8)))
    assert all(r.status_code == 201 for r in responses)
    async with build_sessionmaker(db_engine)() as db:
        numbers = sorted((await db.execute(select(ResumeVersion.version_no))).scalars())
    assert numbers == list(range(1, 9))
    assert (await student.get(f"{API}/resumes/{resume}")).json()["resume"]["latest_version_no"] == 8


async def test_duplicate_certificate_events_leave_one_certificate(db_engine, settings):
    sessionmaker = build_sessionmaker(db_engine)
    payload = certificate_payload()
    results = await asyncio.gather(*(deliver(sessionmaker, settings, "certificate.issued", payload) for _ in range(5)), return_exceptions=True)
    failures = [r for r in results if isinstance(r, Exception)]
    assert all(isinstance(f, IntegrityError) for f in failures)  # a race loses on the unique key ...
    for _ in failures:  # ... and the stream redelivers what was not acknowledged
        await deliver(sessionmaker, settings, "certificate.issued", payload)
    async with sessionmaker() as db:
        certificates = (await db.execute(select(func.count()).select_from(ProfileItem).where(ProfileItem.kind == "certificate"))).scalar_one()
        courses = (await db.execute(select(func.count()).select_from(ProfileItem).where(ProfileItem.kind == "course"))).scalar_one()
    assert (certificates, courses) == (1, 1)


async def test_percentile_query_on_postgresql(db_engine, settings):
    sessionmaker = build_sessionmaker(db_engine)
    users = [STUDENT + n for n in range(1, 5)]
    for n, user in enumerate(users):
        await deliver(sessionmaker, settings, "attempt.finalized", attempt_payload(500 + n, user=user, percent=50.0 + 10 * n))
    from app.services.profile_service import ProfileService

    async with sessionmaker() as db:
        percentile, cohort = await ProfileService(db, settings)._percentile(1755000000051001, 70.0)
    assert (percentile, cohort) == (62, 4)  # 2 below + half of 1 equal, of 4
