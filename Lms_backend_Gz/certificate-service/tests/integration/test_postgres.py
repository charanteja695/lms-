"""What only a real PostgreSQL can prove: the migration (applied up, down and up again, then checked for drift against the
models), the partial unique index that keeps one live certificate per student and course, and ``SKIP LOCKED`` claiming."""

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
from app.models.certificate import Certificate
from app.models.outbox_event import OutboxEvent
from app.services.pdf_service import PdfService
from tests.conftest import _settings, passed_payload

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def pg_url(tmp_path_factory) -> Iterator[str]:
    pgserver = pytest.importorskip("pgserver")
    server = pgserver.get_server(tmp_path_factory.mktemp("pg_service"), cleanup_mode="delete")
    server.psql("CREATE DATABASE lms_certificate;")
    yield server.get_uri().rsplit("/", 1)[0].replace("postgresql://", "postgresql+asyncpg://", 1) + "/lms_certificate"
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


async def test_concurrent_deliveries_of_one_pass_issue_one_certificate(send_event, directory, sessionmaker):
    await directory()
    await asyncio.gather(*(send_event("course.passed", passed_payload(), event_id=f"evt-{n}") for n in range(6)))
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count()).select_from(Certificate))).scalar_one() == 1
        assert (await db.execute(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.event_type == "certificate.issued"))).scalar_one() == 1


async def test_concurrent_pdf_workers_never_render_the_same_certificate(send_event, directory, sessionmaker, settings):
    await directory()
    for n in range(8):
        await send_event("course.passed", passed_payload(student=1755000000007200 + n, attempt=1755000000009200 + n))

    async def claim() -> list[int]:
        async with sessionmaker() as db:
            return await PdfService(db, settings).claim(3)

    taken = [c for batch in await asyncio.gather(*(claim() for _ in range(4))) for c in batch]
    assert len(taken) == len(set(taken)) == 8


async def test_the_whole_flow_renders_and_stores_a_pdf_on_postgresql(client, who, send_event, directory, render, s3_bucket):
    await directory()
    await send_event("course.passed", passed_payload())
    await render()
    who.student()
    certificate = (await client.get("/api/v1/certificates")).json()["certificates"][0]
    assert certificate["pdf_status"] == "ready"
    assert (await client.get(f"/api/v1/public/verify/{certificate['verification_code']}")).json()["verification"]["valid"] is True
