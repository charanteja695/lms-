"""What only a real PostgreSQL can prove: the migration (up, down and up again, then checked for drift against the models),
JSON null stored as SQL NULL (the "not embedded yet" filter), and row locks under real concurrency — one lease per job,
consecutive message numbers, and a hint ladder that climbs exactly once per request."""

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
from app.models.content import ContentChunk
from app.models.conversation import Escalation, HintProgress, Message
from app.services.escalation_service import EscalationService
from app.services.index_service import IndexService
from tests.conftest import PRACTICE_FIB, _settings, ask, published_payload, start_conversation

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def pg_url(tmp_path_factory) -> Iterator[str]:
    pgserver = pytest.importorskip("pgserver")
    server = pgserver.get_server(tmp_path_factory.mktemp("pg_service"), cleanup_mode="delete")
    server.psql("CREATE DATABASE lms_ai_tutor;")
    yield server.get_uri().rsplit("/", 1)[0].replace("postgresql://", "postgresql+asyncpg://", 1) + "/lms_ai_tutor"
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


async def test_unembedded_chunks_are_sql_null_and_the_whole_flow_runs_on_postgresql(client, who, course, sessionmaker):
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count(ContentChunk.id)).where(ContentChunk.embedding.is_(None)))).scalar_one() == 0  # the course fixture embedded them
    who.student()
    conversation = await start_conversation(client)
    answer = (await ask(client, conversation, "What is a base case in recursion?")).json()["turn"]["assistant_message"]
    assert answer["kind"] == "answer" and answer["citations"][0]["item_title"] == "Recursion basics"


async def test_new_chunks_are_null_until_embedded(send_event, sessionmaker):
    await send_event("course.published", published_payload())
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count(ContentChunk.id)).where(ContentChunk.embedding.is_(None)))).scalar_one() == 3


async def test_concurrent_workers_never_index_the_same_version(send_event, sessionmaker, settings):
    for n in range(6):
        await send_event("course.published", published_payload(version=1755000000022000 + n, course=1755000000023000 + n))

    async def claim() -> list:
        async with sessionmaker() as db:
            return await IndexService(db, settings).claim(2)

    taken = [job for batch in await asyncio.gather(*(claim() for _ in range(4))) for job in batch]
    assert len(taken) == len(set(taken)) == 6


async def test_concurrent_workers_never_deliver_the_same_escalation(client, who, course, sessionmaker, settings):
    who.student()
    for _ in range(6):
        conversation = await start_conversation(client)
        await ask(client, conversation, "I want a refund")

    async def claim() -> list:
        async with sessionmaker() as db:
            return await EscalationService(db, settings).claim(2)

    taken = [row for batch in await asyncio.gather(*(claim() for _ in range(4))) for row in batch]
    assert len(taken) == len(set(taken)) == 6
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count(Escalation.id)))).scalar_one() == 6


async def test_concurrent_messages_in_one_conversation_get_consecutive_numbers(client, who, course, sessionmaker):
    who.student()
    conversation = await start_conversation(client)
    responses = await asyncio.gather(*(ask(client, conversation, f"What is a base case in recursion? ({n})") for n in range(5)))
    assert all(r.status_code == 200 for r in responses)
    async with sessionmaker() as db:
        numbers = sorted((await db.execute(select(Message.seq))).scalars().all())
    assert numbers == list(range(1, 11))


async def test_concurrent_hint_requests_each_climb_the_ladder_exactly_once(client, who, course, sessionmaker):
    who.student()
    conversation = await start_conversation(client)
    context = {"item_id": str(PRACTICE_FIB), "hint_request": True}
    responses = await asyncio.gather(*(ask(client, conversation, "hint please", context=context) for _ in range(3)))
    assert all(r.status_code == 200 for r in responses)
    levels = sorted(r.json()["turn"]["assistant_message"]["hint_level"] for r in responses)
    assert levels == [1, 2, 3]
    async with sessionmaker() as db:
        assert (await db.execute(select(HintProgress.level))).scalar_one() == 3
