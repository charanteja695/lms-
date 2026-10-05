"""What only a real PostgreSQL can prove: the migration (up, down and up again, then checked for drift against
the models), and behaviour under real concurrency — two redeliveries of the same event, and two workers
recomputing the same rollup day at once, must never double-count."""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.aggregations.rollup import recompute_days
from app.core.config import Settings
from app.core.time import utcnow
from app.db.session import build_engine, build_sessionmaker
from app.models import Base
from app.models.fact import DailyRollup, EventFact
from app.services.ingest_service import ingest
from tests.conftest import _settings

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres

ORG = 1755000000122001


@pytest.fixture(scope="module")
def pg_url(tmp_path_factory) -> Iterator[str]:
    pgserver = pytest.importorskip("pgserver")
    server = pgserver.get_server(tmp_path_factory.mktemp("pg_service"), cleanup_mode="delete")
    server.psql("CREATE DATABASE lms_analytics;")
    yield server.get_uri().rsplit("/", 1)[0].replace("postgresql://", "postgresql+asyncpg://", 1) + "/lms_analytics"
    server.cleanup()


def alembic(pg_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env={**os.environ, "DATABASE_URL": pg_url}, capture_output=True, text=True, check=False)  # noqa: S603


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
def sessionmaker(db_engine: AsyncEngine):
    return build_sessionmaker(db_engine)


async def test_the_same_event_id_ingested_twice_at_once_produces_one_fact(sessionmaker):
    """Two workers redelivering the same event (the router's normal at-least-once guarantee) must not both
    win: `EventFact.event_id` is unique, so only one insert survives."""

    async def attempt() -> bool:
        async with sessionmaker() as db:
            await ingest(db, event_id="race-1", event_type="certificate.issued", occurred_time=utcnow(), payload={"certificate_id": "1", "student_user_id": "1", "organization_id": str(ORG)})
            try:
                await db.commit()
                return True
            except Exception:
                await db.rollback()
                return False

    results = await asyncio.gather(*(attempt() for _ in range(5)))
    async with sessionmaker() as db:
        count = int((await db.execute(select(func.count()).select_from(EventFact).where(EventFact.event_id == "race-1"))).scalar_one())
    assert count == 1
    assert sum(results) >= 1  # at least one attempt succeeded; the rest hit the unique constraint


async def test_two_workers_recomputing_the_same_rollup_day_at_once_leave_one_consistent_row(sessionmaker):
    async with sessionmaker() as db:
        for i in range(4):
            await ingest(db, event_id=f"evt-{i}", event_type="certificate.issued", occurred_time=utcnow(), payload={"certificate_id": str(i), "student_user_id": str(i), "organization_id": str(ORG)})
        await db.commit()

    async def recompute() -> None:
        async with sessionmaker() as db:
            await recompute_days(db, [utcnow().date()])

    await asyncio.gather(*(recompute() for _ in range(3)))

    async with sessionmaker() as db:
        rows = list((await db.execute(select(DailyRollup).where(DailyRollup.event_type == "certificate.issued"))).scalars())
        assert len(rows) == 1 and rows[0].count == 4  # never duplicated, never lost
