import json
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from lms_common.auth import AccessTokenClaims
from lms_common.events import Event
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.api.deps import _authenticate, get_provider_registry
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.events.consumers.router import dispatch
from app.main import create_app
from app.models import Base
from app.providers.base import ChatChunk, ChatRequest, ChatResult, EmbedRequest, EmbedResult
from app.providers.registry import ProviderRegistry

ORG_A, ORG_B = 1755000000010001, 1755000000010002
USER = 1755000000010101
AI_MANAGER, OTHER_MANAGER, STAFF_A = 1755000000010102, 1755000000010103, 1755000000010104
INTERNAL_TOKEN = "test-internal-service-token-0123456789"


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "ENVIRONMENT": "test",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "REDIS_URL": "redis://localhost:6379/15",
        "DOCS_ENABLED": False,
        "RATE_LIMIT_ENABLED": False,
        "LOG_JSON": False,
        "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "VOYAGE_API_KEY": "voyage-test",
        "DEFAULT_MONTHLY_TOKEN_LIMIT": 100_000,
        "DEFAULT_MONTHLY_REQUEST_LIMIT": 1_000,
        "DEFAULT_MONTHLY_BUDGET_CENTS": 100_000,
    }
    values.update(overrides)
    return Settings(**values)


def make_claims(*, user_id: int, role: str = "student", organization_id: int | None = None, scopes: tuple[str, ...] = ()) -> AccessTokenClaims:
    now = datetime.now(UTC)
    return AccessTokenClaims(
        user_id=user_id, session_id=1755000000010002, role=role, organization_id=organization_id,
        organization_type="institution" if organization_id else None, scopes=scopes, token_version=0,
        token_id="test-token", issued_at=int(now.timestamp()), expires_at=now,
    )


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
async def redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
def fake_chat() -> "FakeChatProvider":
    return FakeChatProvider()


@pytest.fixture
def fake_embedding() -> "FakeEmbeddingProvider":
    return FakeEmbeddingProvider()


@pytest.fixture
def registry(fake_chat: "FakeChatProvider", fake_embedding: "FakeEmbeddingProvider") -> ProviderRegistry:
    return ProviderRegistry.for_testing(chat={"anthropic": fake_chat}, embedding={"voyage": fake_embedding})


@pytest.fixture
async def app(db_engine, sessionmaker, settings, redis, registry):
    fastapi_app = create_app(settings)
    fastapi_app.state.engine, fastapi_app.state.sessionmaker, fastapi_app.state.redis = db_engine, sessionmaker, redis
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    fastapi_app.dependency_overrides[get_provider_registry] = lambda: registry
    yield fastapi_app


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def internal_headers() -> dict[str, str]:
    return {"X-Internal-Service-Token": INTERNAL_TOKEN}


@pytest.fixture
def act_as(app) -> Callable[..., AccessTokenClaims]:
    def _set(user_id: int, *, role: str = "admin", organization_id: int | None = None, scopes: tuple[str, ...] = ()) -> AccessTokenClaims:
        claims = make_claims(user_id=user_id, role=role, organization_id=organization_id, scopes=scopes)
        app.dependency_overrides[_authenticate] = lambda: claims
        return claims

    yield _set
    app.dependency_overrides.pop(_authenticate, None)


class Identities:
    def __init__(self, act_as: Callable[..., AccessTokenClaims]) -> None:
        self._act_as = act_as

    def ai_manager(self, user_id: int = AI_MANAGER):
        return self._act_as(user_id, role="admin", scopes=("ai.manage",))

    def other_ai_manager(self, user_id: int = OTHER_MANAGER):
        return self._act_as(user_id, role="admin", scopes=("ai.manage",))

    def staff(self, user_id: int = STAFF_A, organization_id: int = ORG_A):
        return self._act_as(user_id, role="staff", organization_id=organization_id)

    def student(self, user_id: int = USER):
        return self._act_as(user_id, role="student")


@pytest.fixture
def who(act_as) -> Identities:
    return Identities(act_as)


@pytest.fixture
def send_event(sessionmaker, settings) -> Callable[..., Any]:
    """Deliver an event the way the worker's consumer does: through the router, in one transaction."""

    async def _send(event_type: str, payload: dict[str, Any], *, event_id: str | None = None) -> None:
        event = Event(event_id=event_id or uuid.uuid4().hex, event_type=event_type, aggregate_type="x", occurred_time=datetime.now(UTC), payload=json.loads(json.dumps(payload)))
        async with sessionmaker() as db:
            await dispatch(db, event, settings)
            await db.commit()

    return _send


class FakeChatProvider:
    """A scripted chat provider: queue `ChatResult`s (or an exception) with `queue_result`/`queue_error`, or
    let `complete`/`stream` use their defaults. Every call is recorded in `.calls`."""

    name = "anthropic"

    def __init__(self) -> None:
        self.calls: list[ChatRequest] = []
        self._results: list[ChatResult | Exception] = []
        self._stream_chunks: list[ChatChunk] | None = None

    def queue_result(self, result: ChatResult) -> None:
        self._results.append(result)

    def queue_error(self, exc: Exception) -> None:
        self._results.append(exc)

    def queue_stream(self, chunks: list[ChatChunk]) -> None:
        self._stream_chunks = chunks

    async def complete(self, request: ChatRequest) -> ChatResult:
        self.calls.append(request)
        if self._results:
            outcome = self._results.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        return ChatResult(content="Default fake reply.", model=request.model, prompt_tokens=10, completion_tokens=5, stop_reason="end_turn")

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        self.calls.append(request)
        if self._results and isinstance(self._results[0], Exception):
            raise self._results.pop(0)  # type: ignore[misc]
        chunks = self._stream_chunks or [ChatChunk(delta_text="Hello"), ChatChunk(delta_text=" there"), ChatChunk(delta_text="", done=True, stop_reason="end_turn", prompt_tokens=10, completion_tokens=2)]
        for chunk in chunks:
            yield chunk


class FakeEmbeddingProvider:
    name = "voyage"

    def __init__(self) -> None:
        self.calls: list[EmbedRequest] = []
        self._error: Exception | None = None

    def queue_error(self, exc: Exception) -> None:
        self._error = exc

    async def embed(self, request: EmbedRequest) -> EmbedResult:
        self.calls.append(request)
        if self._error is not None:
            error, self._error = self._error, None
            raise error
        return EmbedResult(vectors=[[0.1, 0.2, 0.3] for _ in request.texts], model=request.model, tokens=len(request.texts) * 10)
