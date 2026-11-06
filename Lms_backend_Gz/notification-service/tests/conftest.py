from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from itertools import count
from typing import Any

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from lms_common.auth import AccessTokenClaims
from lms_common.events import Event
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.api.deps import _authenticate
from app.channels.email import EmailMessage
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.events.consumers.router import dispatch
from app.main import create_app
from app.models import Base

TEST_SESSION_ID = 1755000000006002
TEST_ORG_ID = 1755000000006003
TEST_COURSE_ID = 1755000000006004
TEST_VERSION_ID = 1755000000006005
STUDENT_ID = 1755000000006101
HEAD_ID = 1755000000006102
OTHER_HEAD_ID = 1755000000006103
SUPER_ADMIN_ID = 1755000000006104


def _settings(**overrides: Any) -> Settings:
    return Settings(
        ENVIRONMENT="test",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        REDIS_URL="redis://localhost:6379/15",
        DOCS_ENABLED=False,
        RATE_LIMIT_ENABLED=False,
        LOG_JSON=False,
        DELIVERY_MAX_ATTEMPTS=3,
        DELIVERY_RETRY_BASE_SECONDS=60,
        **overrides,
    )


def make_claims(*, user_id: int, role: str, organization_id: int | None = None) -> AccessTokenClaims:
    now = datetime.now(UTC)
    return AccessTokenClaims(
        user_id=user_id,
        session_id=TEST_SESSION_ID,
        role=role,
        organization_id=organization_id,
        organization_type="institution" if organization_id else None,
        scopes=(),
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
def sessionmaker(db_engine: AsyncEngine) -> async_sessionmaker:
    return build_sessionmaker(db_engine)


@pytest.fixture
def settings() -> Settings:
    return _settings()


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
def authed(app) -> Callable[..., AccessTokenClaims]:
    def _set(*, user_id: int, role: str = "student", organization_id: int | None = None) -> AccessTokenClaims:
        claims = make_claims(user_id=user_id, role=role, organization_id=organization_id)
        app.dependency_overrides[_authenticate] = lambda: claims
        return claims

    yield _set
    app.dependency_overrides.pop(_authenticate, None)


_event_numbers = count(1)


def make_event(event_type: str, payload: dict[str, Any], *, event_id: str | None = None) -> Event:
    return Event(
        event_id=event_id or f"evt-{next(_event_numbers)}",
        event_type=event_type,
        aggregate_type="test",
        occurred_time=datetime.now(UTC),
        payload=payload,
    )


@pytest.fixture
def publish(sessionmaker: async_sessionmaker, settings: Settings) -> Callable[..., Any]:
    """Runs an event through the same dispatch + commit the worker does."""

    async def _publish(event_type: str, payload: dict[str, Any], *, event_id: str | None = None) -> Event:
        event = make_event(event_type, payload, event_id=event_id)
        async with sessionmaker() as db:
            await dispatch(db, event, settings)
            await db.commit()
        return event

    return _publish


def user_payload(user_id: int, *, role: str = "student", email: str | None = "x@example.com", status: str = "active",
                 first_name: str = "Asha", organization_id: int | None = TEST_ORG_ID) -> dict[str, Any]:
    """Mirrors user-management's UserRepository.event_payload."""
    return {
        "user_id": str(user_id),
        "email": email,
        "username": f"user{user_id}",
        "first_name": first_name,
        "last_name": "Rao",
        "role": role,
        "status": status,
        "organization_id": str(organization_id) if organization_id else None,
    }


def course_payload() -> dict[str, Any]:
    """The part of catalog-service's course.published payload this service reads."""
    return {"course_id": str(TEST_COURSE_ID), "version_id": str(TEST_VERSION_ID), "title": "Python Basics", "slug": "python-basics"}


class RecordingEmailSender:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []
        self.fail_with: Exception | None = None

    async def send(self, message: EmailMessage) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.sent.append(message)


@pytest.fixture
def email_sender() -> RecordingEmailSender:
    return RecordingEmailSender()
