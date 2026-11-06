from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from lms_common.auth import AccessTokenClaims
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.deps import _authenticate
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.main import create_app
from app.models import Base

TEST_USER_ID = 1755000000000001
TEST_SESSION_ID = 1755000000000002


def _settings() -> Settings:
    return Settings(
        ENVIRONMENT="test",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        REDIS_URL="redis://localhost:6379/15",
        DOCS_ENABLED=False,
        RATE_LIMIT_ENABLED=False,
        LOG_JSON=False,
    )


def make_claims(*, user_id: int = TEST_USER_ID, scopes: tuple[str, ...] = (), role: str = "admin") -> AccessTokenClaims:
    now = datetime.now(UTC)
    return AccessTokenClaims(
        user_id=user_id,
        session_id=TEST_SESSION_ID,
        role=role,
        organization_id=None,
        organization_type=None,
        scopes=scopes,
        token_version=0,
        token_id="test-token",
        issued_at=int(now.timestamp()),
        expires_at=now,
    )


@pytest.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = build_engine(_settings())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def app(db_engine: AsyncEngine):
    settings = _settings()
    fastapi_app = create_app(settings)
    fastapi_app.state.engine = db_engine
    fastapi_app.state.sessionmaker = build_sessionmaker(db_engine)
    fastapi_app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    # get_settings() is a process-wide lru_cache singleton (correct for production, where it's
    # populated once at startup) — override it per app instance so tests aren't silently
    # governed by whatever settings some earlier import cached.
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    yield fastapi_app
    await fastapi_app.state.redis.aclose()


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def authed(app) -> Callable[..., AccessTokenClaims]:
    """Bypass real JWKS/Redis verification: install fake, already-verified claims."""

    def _set(*, scopes: tuple[str, ...] = (), user_id: int = TEST_USER_ID, role: str = "admin") -> AccessTokenClaims:
        claims = make_claims(user_id=user_id, scopes=scopes, role=role)
        app.dependency_overrides[_authenticate] = lambda: claims
        return claims

    yield _set
    app.dependency_overrides.pop(_authenticate, None)
