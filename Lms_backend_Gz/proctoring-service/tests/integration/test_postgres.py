"""What only a real PostgreSQL can prove: the migration (applied up, down and up again, then checked for drift against the
models), row locks under real concurrency (one session per attempt, one decision per session), and ``SKIP LOCKED`` claiming."""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.time import utcnow
from app.db.session import build_engine
from app.models import Base
from app.models.case import IntegrityCase
from app.models.outbox_event import OutboxEvent
from app.models.session import ProctorSession, Snapshot
from app.services.snapshot_service import SnapshotService
from tests.conftest import ATTEMPT, TEST_BASIC, _settings, started_payload
from tests.integration.test_live_session import event, go_live

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def pg_url(tmp_path_factory) -> Iterator[str]:
    pgserver = pytest.importorskip("pgserver")
    server = pgserver.get_server(tmp_path_factory.mktemp("pg_service"), cleanup_mode="delete")
    server.psql("CREATE DATABASE lms_proctoring;")
    yield server.get_uri().rsplit("/", 1)[0].replace("postgresql://", "postgresql+asyncpg://", 1) + "/lms_proctoring"
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


async def test_the_whole_flow_runs_on_postgresql(client, who, tests_published, send_event, work, sessionmaker):
    session_id = await go_live(client, who, tests_published, send_event)
    await client.post(f"/api/v1/sessions/{session_id}/events", json={"events": [event("tab_switch")] * 5 + [event("fullscreen_exit")] * 2})
    await send_event("attempt.submitted", {"attempt_id": str(ATTEMPT), "proctoring_level": "basic", "submit_reason": "manual"})
    await work.finalize()
    who.exam_manager()
    (case,) = (await client.get("/api/v1/cases")).json()["cases"]
    assert case["status"] == "open" and case["risk_score"] == 46


async def test_the_same_attempt_started_twice_at_once_gets_one_session(tests_published, send_event, sessionmaker):
    await tests_published()
    await asyncio.gather(*(send_event("attempt.started", started_payload(), event_id=f"evt-{n}") for n in range(6)))
    async with sessionmaker() as db:
        sessions = (await db.execute(select(ProctorSession).where(ProctorSession.attempt_id == ATTEMPT))).scalars().all()
    assert len(sessions) == 1 and sessions[0].status == "active"


async def test_concurrent_deciders_take_one_decision_per_session(client, who, tests_published, send_event, sessionmaker, settings):
    from app.services.case_service import finalize_sweep

    session_id = await go_live(client, who, tests_published, send_event)
    await client.post(f"/api/v1/sessions/{session_id}/events", json={"events": [event("window_blur")]})
    await send_event("attempt.submitted", {"attempt_id": str(ATTEMPT), "proctoring_level": "basic", "submit_reason": "manual"})
    await asyncio.gather(*(finalize_sweep(sessionmaker, settings) for _ in range(4)))
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count()).select_from(IntegrityCase))).scalar_one() == 1
        decided = (await db.execute(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.event_type == "integrity.decided"))).scalar_one()
    assert decided == 1  # cleared once, however many workers raced


async def test_concurrent_claims_never_hand_the_same_snapshot_to_two_analysers(sessionmaker, settings):
    import uuid
    from datetime import timedelta

    async with sessionmaker() as db:
        session = ProctorSession(public_id=1755000000000700, test_id=TEST_BASIC, user_id=1, level="strict", risk_breakdown={})
        db.add(session)
        await db.flush()
        for n in range(9):
            db.add(Snapshot(public_id=1755000000000800 + n, session_id=session.id, kind="periodic", s3_key=f"k{n}", taken_at=utcnow(), delete_after=utcnow() + timedelta(days=1)))
        await db.commit()

    async def claim() -> list[int]:
        async with sessionmaker() as db:
            return await SnapshotService(db, settings).claim(3)

    taken = [c for batch in await asyncio.gather(*(claim() for _ in range(4))) for c in batch]
    assert len(taken) == len(set(taken)) == 9
    assert uuid and update
