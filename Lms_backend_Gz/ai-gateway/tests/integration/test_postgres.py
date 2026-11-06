"""What only a real PostgreSQL can prove: the migration (applied up, down and up again, then checked for drift
against the models), and that ``QuotaService.reserve()``'s row lock actually serialises concurrent spenders of
the same org's quota instead of letting them all squeeze under the limit together."""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import Settings
from app.core.exceptions import QuotaExceededError
from app.core.time import period_of, utcnow
from app.db.session import build_engine, build_sessionmaker
from app.models import Base
from app.services.quota_service import QuotaService
from tests.conftest import ORG_A, _settings

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def pg_url(tmp_path_factory) -> Iterator[str]:
    pgserver = pytest.importorskip("pgserver")
    server = pgserver.get_server(tmp_path_factory.mktemp("pg_service"), cleanup_mode="delete")
    server.psql("CREATE DATABASE lms_ai_gateway;")
    yield server.get_uri().rsplit("/", 1)[0].replace("postgresql://", "postgresql+asyncpg://", 1) + "/lms_ai_gateway"
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
    return _settings(DATABASE_URL=migrated, DEFAULT_MONTHLY_TOKEN_LIMIT=100, DEFAULT_MONTHLY_REQUEST_LIMIT=1_000, DEFAULT_MONTHLY_BUDGET_CENTS=1_000_000)


@pytest.fixture
async def db_engine(settings: Settings) -> AsyncIterator[AsyncEngine]:
    engine = build_engine(settings)
    async with engine.begin() as conn:
        tables = ", ".join(f'"{name}"' for name in Base.metadata.tables)
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))  # noqa: S608
    yield engine
    await engine.dispose()


@pytest.fixture
def sessionmaker(db_engine: AsyncEngine) -> async_sessionmaker:
    return build_sessionmaker(db_engine)


async def test_concurrent_reservations_never_spend_past_the_token_limit(sessionmaker, settings) -> None:
    """5 concurrent callers each try to reserve 30 tokens against a 100-token limit: at most 3 can fit (90 <= 100,
    a 4th would make 120 > 100). Without the row lock in QuotaService._usage_row_locked, a lost-update race would
    let all 5 (or some other wrong number) through."""

    async def attempt() -> bool:
        async with sessionmaker() as db:
            try:
                await QuotaService(db, settings).reserve(organization_id=ORG_A, estimated_tokens=30)
                return True
            except QuotaExceededError:
                return False

    results = await asyncio.gather(*(attempt() for _ in range(5)))
    assert sum(results) == 3

    async with sessionmaker() as db:
        row = await QuotaService(db, settings)._select_locked(ORG_A, period_of(utcnow()))
        assert row is not None
        assert row.completion_tokens_used == 90 and row.requests_used == 3


async def test_concurrent_first_time_reservations_for_the_same_org_and_period_do_not_conflict(sessionmaker, settings) -> None:
    """The very first reservation for an org+period has no row yet: several callers racing to insert it must not
    raise an unhandled IntegrityError (see the savepoint fallback in QuotaService._usage_row_locked)."""

    async def attempt() -> None:
        async with sessionmaker() as db:
            await QuotaService(db, settings).reserve(organization_id=ORG_A, estimated_tokens=1)

    await asyncio.gather(*(attempt() for _ in range(8)))

    async with sessionmaker() as db:
        row = await QuotaService(db, settings)._select_locked(ORG_A, period_of(utcnow()))
        assert row is not None and row.requests_used == 8
