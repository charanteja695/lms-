from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from lms_common.auth import AccessTokenClaims
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.api.deps import _authenticate
from app.core.config import Settings, get_settings
from app.core.crypto import SecretCipher
from app.db.session import build_engine, build_sessionmaker
from app.engines.base import ExecutionRequest, ExecutionResult, Outcome
from app.engines.factory import build_engine as build_execution_engine
from app.main import create_app
from app.models import Base
from app.models.run import Run
from app.models.submission import Submission
from app.services.judge_service import JudgeService
from app.services.language_service import LanguageService
from app.services.queue_service import QueueService

LANGUAGES_FILE = Path(__file__).resolve().parents[1] / "runtimes" / "languages.json"
TEST_SESSION_ID = 1755000000007002
ORG_A = 1755000000007003
ORG_B = 1755000000007004
STUDENT = 1755000000007101
STUDENT_2 = 1755000000007102
AUTHOR = 1755000000007103
REVIEWER = 1755000000007104
SUPER_ADMIN = 1755000000007105
INTERNAL_TOKEN = "test-internal-service-token"


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "ENVIRONMENT": "test",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "REDIS_URL": "redis://localhost:6379/15",
        "DOCS_ENABLED": False,
        "RATE_LIMIT_ENABLED": False,
        "LOG_JSON": False,
        "EXECUTION_ENGINE": "local",
        "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
        "RESULT_POLL_INTERVAL_SECONDS": 0.02,
        "WORKER_POLL_SECONDS": 0.02,
        "JOB_MAX_ATTEMPTS": 2,
        "SIMILARITY_MIN_TOKENS": 10,
    }
    values.update(overrides)
    return Settings(**values)


def make_claims(*, user_id: int, role: str, organization_id: int | None, scopes: tuple[str, ...]) -> AccessTokenClaims:
    now = datetime.now(UTC)
    return AccessTokenClaims(
        user_id=user_id,
        session_id=TEST_SESSION_ID,
        role=role,
        organization_id=organization_id,
        organization_type="institution" if organization_id else None,
        scopes=scopes,
        token_version=0,
        token_id="test-token",
        issued_at=int(now.timestamp()),
        expires_at=now,
    )


class ScriptedEngine:
    """A deterministic stand-in for an engine: ``behave`` maps a request to a result (default: ran, no output),
    and every request is recorded. Lets a test exercise judging without depending on real programs."""

    def __init__(self) -> None:
        self.calls: list[ExecutionRequest] = []
        self.behave: Callable[[ExecutionRequest], ExecutionResult | Exception] = lambda request: ExecutionResult(Outcome.OK)

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls.append(request)
        outcome = self.behave(request)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = build_engine(_settings())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def sessionmaker(db_engine: AsyncEngine) -> async_sessionmaker:
    return build_sessionmaker(db_engine)


@pytest.fixture
def settings() -> Settings:
    return _settings()


@pytest.fixture
def cipher(settings: Settings) -> SecretCipher:
    return SecretCipher.from_settings(settings)


@pytest.fixture
async def app(db_engine: AsyncEngine, sessionmaker: async_sessionmaker, settings: Settings):
    fastapi_app = create_app(settings)
    fastapi_app.state.engine = db_engine
    fastapi_app.state.sessionmaker = sessionmaker
    fastapi_app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    yield fastapi_app
    await fastapi_app.state.redis.aclose()


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def act_as(app) -> Callable[..., AccessTokenClaims]:
    """Sign the test client in as someone. Roles/scopes are exactly what user-management would put in a token."""

    def _set(user_id: int, *, role: str = "student", organization_id: int | None = ORG_A, scopes: tuple[str, ...] = ()) -> AccessTokenClaims:
        claims = make_claims(user_id=user_id, role=role, organization_id=organization_id, scopes=scopes)
        app.dependency_overrides[_authenticate] = lambda: claims
        return claims

    yield _set
    app.dependency_overrides.pop(_authenticate, None)


@pytest.fixture
def as_student(act_as) -> Callable[..., AccessTokenClaims]:
    return lambda user_id=STUDENT, organization_id=ORG_A: act_as(user_id, role="student", organization_id=organization_id)


@pytest.fixture
def as_author(act_as) -> Callable[[], AccessTokenClaims]:
    return lambda: act_as(AUTHOR, role="admin", organization_id=None, scopes=("content.author",))


@pytest.fixture
def as_reviewer(act_as) -> Callable[[], AccessTokenClaims]:
    return lambda: act_as(REVIEWER, role="admin", organization_id=None, scopes=("content.review",))


@pytest.fixture
def as_super_admin(act_as) -> Callable[[], AccessTokenClaims]:
    return lambda: act_as(SUPER_ADMIN, role="super_admin", organization_id=None)


@pytest.fixture(autouse=True)
async def languages(sessionmaker: async_sessionmaker) -> None:
    """The catalogue, as `python -m app.cli sync-languages` would load it. postgresql needs a sandbox cluster
    (see runtimes/sql), so it stays disabled as shipped."""
    async with sessionmaker() as db:
        await LanguageService(db).sync_from_file(LANGUAGES_FILE)


@pytest.fixture
def scripted_engine() -> ScriptedEngine:
    return ScriptedEngine()


@pytest.fixture
def real_engine(settings: Settings):
    return build_execution_engine(settings)


@pytest.fixture
def judge_with(sessionmaker: async_sessionmaker, settings: Settings, cipher: SecretCipher) -> Callable[..., JudgeService]:
    return lambda engine, **overrides: JudgeService(sessionmaker, engine, replace_settings(settings, overrides), cipher)


def replace_settings(settings: Settings, overrides: dict[str, Any]) -> Settings:
    return settings.model_copy(update=overrides) if overrides else settings


DrainFn = Callable[..., Awaitable[None]]


@pytest.fixture
def drain(sessionmaker: async_sessionmaker, settings: Settings) -> Callable[[JudgeService], Awaitable[None]]:
    """Process everything currently queued, the way the worker would: claim, then judge. Highest lane first."""

    async def _drain(judge: JudgeService) -> None:
        async with sessionmaker() as db:
            submissions = await QueueService(db, settings).claim(Submission, 100)
        for submission in submissions:
            await judge.process_submission(submission.id)
        async with sessionmaker() as db:
            runs = await QueueService(db, settings).claim(Run, 100)
        for run in runs:
            await judge.process_run(run.id)

    return _drain


ProblemFactory = Callable[..., Awaitable[int]]

SUM_SOLUTION = "a, b = map(int, input().split())\nprint(a + b)\n"


@pytest.fixture
def make_problem(client: AsyncClient, as_author, act_as) -> ProblemFactory:
    """Author and publish a problem through the API. Returns its public id and leaves the client signed out of
    the author role only if the caller switches; tests always sign in as who they need next."""

    async def _make(
        *,
        cases: list[tuple[str, str]] | list[dict[str, Any]] | None = None,
        publish: bool = True,
        **fields: Any,
    ) -> int:
        as_author()
        body: dict[str, Any] = {"title": "Sum of two numbers", "statement": "Print a + b.", "time_limit_ms": 2000, **fields}
        created = await client.post("/api/v1/problems", json=body)
        assert created.status_code == 201, created.text
        problem_id = created.json()["problem"]["problem_id"]
        for case in cases if cases is not None else [("1 2\n", "3\n"), ("10 20\n", "30\n")]:
            payload = case if isinstance(case, dict) else {"input": case[0], "expected": case[1]}
            added = await client.post(f"/api/v1/problems/{problem_id}/test-cases", json=payload)
            assert added.status_code == 201, added.text
        if publish:
            published = await client.post(f"/api/v1/problems/{problem_id}/publish")
            assert published.status_code == 200, published.text
        return int(problem_id)

    return _make
