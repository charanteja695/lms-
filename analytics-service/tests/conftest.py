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

from app.aggregations.rollup import recompute_days
from app.api.deps import _authenticate
from app.core.config import Settings, get_settings
from app.core.time import utcnow
from app.db.session import build_engine, build_sessionmaker
from app.events.consumers.router import dispatch
from app.main import create_app
from app.models import Base

INSTITUTION, INSTITUTION_2 = 1755000000110001, 1755000000110002
EMPLOYER, EMPLOYER_2 = 1755000000110011, 1755000000110012
HEAD, STAFF, EMP_ADMIN, RECRUITER = 1755000000110101, 1755000000110102, 1755000000110103, 1755000000110104
SUPER, OTHER_ADMIN, ANALYST, CONTENT_ADMIN, EXAMS_ADMIN, SUPPORT_ADMIN, CAREERS_ADMIN, AI_ADMIN, BILLING_ADMIN = (1755000000110111 + n for n in range(9))
API = "/api/v1"


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "ENVIRONMENT": "test", "DATABASE_URL": "sqlite+aiosqlite:///:memory:", "REDIS_URL": "redis://localhost:6379/15", "DOCS_ENABLED": False, "RATE_LIMIT_ENABLED": False, "LOG_JSON": False,
    }
    values.update(overrides)
    return Settings(**values)


def make_claims(*, user_id: int, role: str, organization_id: int | None, scopes: tuple[str, ...] = ()) -> AccessTokenClaims:
    now = datetime.now(UTC)
    return AccessTokenClaims(
        user_id=user_id, session_id=1755000000110900, role=role, organization_id=organization_id, organization_type="institution" if role in {"student", "staff", "institution_head"} else None,
        scopes=scopes, token_version=0, token_id="test-token", issued_at=int(now.timestamp()), expires_at=now,
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
async def app(db_engine, sessionmaker, settings, redis):
    fastapi_app = create_app(settings)
    fastapi_app.state.engine, fastapi_app.state.sessionmaker, fastapi_app.state.redis = db_engine, sessionmaker, redis
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    yield fastapi_app


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def act_as(app) -> Callable[..., AccessTokenClaims]:
    def _set(user_id: int, *, role: str, organization_id: int | None, scopes: tuple[str, ...] = ()) -> AccessTokenClaims:
        claims = make_claims(user_id=user_id, role=role, organization_id=organization_id, scopes=scopes)
        app.dependency_overrides[_authenticate] = lambda: claims
        return claims

    yield _set
    app.dependency_overrides.pop(_authenticate, None)


class Identities:
    def __init__(self, act_as: Callable[..., AccessTokenClaims]) -> None:
        self._act_as = act_as

    def head(self, user_id: int = HEAD, organization_id: int = INSTITUTION):
        return self._act_as(user_id, role="institution_head", organization_id=organization_id)

    def staff(self, user_id: int = STAFF, organization_id: int = INSTITUTION):
        return self._act_as(user_id, role="staff", organization_id=organization_id)

    def employer_admin(self, user_id: int = EMP_ADMIN, organization_id: int = EMPLOYER):
        return self._act_as(user_id, role="employer_admin", organization_id=organization_id)

    def recruiter(self, user_id: int = RECRUITER, organization_id: int = EMPLOYER):
        return self._act_as(user_id, role="recruiter", organization_id=organization_id)

    def super_admin(self):
        return self._act_as(SUPER, role="super_admin", organization_id=None)

    def other_admin(self):
        return self._act_as(OTHER_ADMIN, role="admin", organization_id=None, scopes=("accounts.manage",))

    def analyst(self):
        return self._act_as(ANALYST, role="admin", organization_id=None, scopes=("analytics.view",))

    def content_admin(self):
        return self._act_as(CONTENT_ADMIN, role="admin", organization_id=None, scopes=("content.review",))

    def exams_admin(self):
        return self._act_as(EXAMS_ADMIN, role="admin", organization_id=None, scopes=("exams.manage",))

    def support_admin(self):
        return self._act_as(SUPPORT_ADMIN, role="admin", organization_id=None, scopes=("support.manage",))

    def careers_admin(self):
        return self._act_as(CAREERS_ADMIN, role="admin", organization_id=None, scopes=("careers.manage",))

    def ai_admin(self):
        return self._act_as(AI_ADMIN, role="admin", organization_id=None, scopes=("ai.manage",))

    def billing_admin(self):
        return self._act_as(BILLING_ADMIN, role="admin", organization_id=None, scopes=("billing.manage",))


@pytest.fixture
def who(act_as) -> Identities:
    return Identities(act_as)


@pytest.fixture
def send_event(sessionmaker) -> Callable[..., Any]:
    """Deliver an event the way the worker's consumer does: through the router, in one transaction."""

    async def _send(event_type: str, payload: dict[str, Any], *, event_id: str | None = None, occurred_time: datetime | None = None) -> None:
        event = Event(event_id=event_id or uuid.uuid4().hex, event_type=event_type, aggregate_type="x", occurred_time=occurred_time or utcnow(), payload=payload)
        async with sessionmaker() as db:
            await dispatch(db, event)
            await db.commit()

    return _send


@pytest.fixture
def rollup(sessionmaker) -> Callable[..., Any]:
    """Recompute DailyRollup for the given days (today by default) from ingested EventFact rows, like the
    worker's periodic tick would."""

    async def _rollup(days: list | None = None) -> int:
        async with sessionmaker() as db:
            return await recompute_days(db, days or [utcnow().date()])

    return _rollup
