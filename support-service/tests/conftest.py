import json
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import fakeredis.aioredis
import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from lms_common.auth import AccessTokenClaims
from lms_common.events import Event
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.api.deps import _authenticate, get_people_client
from app.clients.user_management import UserManagementClient
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.events.consumers.router import dispatch
from app.main import create_app
from app.models import Base

ORG_A, ORG_B = 1755000000030001, 1755000000030002
STUDENT, STUDENT_2 = 1755000000030101, 1755000000030102
SUPPORT, SUPPORT_2, EXAM_TEAM, STAFF_A, STAFF_A2, HEAD_A, STAFF_B, SUPER = (1755000000030100 + n for n in range(3, 11))
COURSE = 1755000000031001
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
        "WORKER_POLL_SECONDS": 0.02,
    }
    values.update(overrides)
    return Settings(**values)


# What user-management puts in a token by default (its permission catalog), for the permissions this service checks.
# What user-management's token carries by default: matrix cells plus the feature keys they imply.
ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "student": ("support.view", "support.create", "support.ask"),
    "staff": ("support_queue.view", "support_queue.update", "support.agent"),
    "institution_head": ("support_queue.view", "support_queue.update", "support_queue.approve", "support.agent", "support.assign"),
}


def make_claims(*, user_id: int, role: str, organization_id: int | None, scopes: tuple[str, ...], defaults: bool = True) -> AccessTokenClaims:
    scopes = (*ROLE_PERMISSIONS.get(role, ()), *scopes) if defaults else scopes  # "defaults": the role's own
    now = datetime.now(UTC)
    return AccessTokenClaims(
        user_id=user_id, session_id=1755000000030002, role=role, organization_id=organization_id,
        organization_type="institution" if organization_id else None, scopes=scopes, token_version=0,
        token_id="test-token", issued_at=int(now.timestamp()), expires_at=now,
        # the test admin looks after both test institutions (support.manage reaches only those for an admin)
        admin_organization_ids=(ORG_A, ORG_B) if role == "admin" else (),
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


class PeopleStub:
    """Stands in for user-management's ``/internal/permission-holders``: everyone holds what their role gives them,
    except the (user, permission) pairs a test removes. ``calls`` records what was asked."""

    def __init__(self) -> None:
        self.removed: set[tuple[int, str]] = set()
        self.calls: list[dict[str, Any]] = []
        self.down = False

    def respond(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            return httpx.Response(503)
        assert request.headers["X-Internal-Service-Token"] == INTERNAL_TOKEN
        body = json.loads(request.content)
        self.calls.append(body)
        held = [u for u in body["user_ids"] if (int(u), body["permission"]) not in self.removed]
        return httpx.Response(200, json={"status": "success", "message": "", "user_ids": held})


@pytest.fixture
def people() -> PeopleStub:
    return PeopleStub()


@pytest.fixture
async def app(db_engine, sessionmaker, settings, redis, people):
    fastapi_app = create_app(settings)
    fastapi_app.state.engine, fastapi_app.state.sessionmaker, fastapi_app.state.redis = db_engine, sessionmaker, redis
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    fastapi_app.dependency_overrides[get_people_client] = lambda: UserManagementClient(settings, transport=httpx.MockTransport(people.respond))
    yield fastapi_app


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def internal_headers() -> dict[str, str]:
    return {"X-Internal-Service-Token": INTERNAL_TOKEN}


@pytest.fixture
def act_as(app) -> Callable[..., AccessTokenClaims]:
    def _set(user_id: int, *, role: str = "student", organization_id: int | None = ORG_A, scopes: tuple[str, ...] = (), defaults: bool = True) -> AccessTokenClaims:
        claims = make_claims(user_id=user_id, role=role, organization_id=organization_id, scopes=scopes, defaults=defaults)
        app.dependency_overrides[_authenticate] = lambda: claims
        return claims

    yield _set
    app.dependency_overrides.pop(_authenticate, None)


class Identities:
    def __init__(self, act_as: Callable[..., AccessTokenClaims]) -> None:
        self._act_as = act_as

    def student(self, user_id: int = STUDENT, organization_id: int | None = ORG_A):
        return self._act_as(user_id, role="student", organization_id=organization_id)

    def support(self, user_id: int = SUPPORT):
        return self._act_as(user_id, role="admin", organization_id=None, scopes=("support.manage",))

    def exam_team(self):
        return self._act_as(EXAM_TEAM, role="admin", organization_id=None, scopes=("exams.manage",))

    def staff(self, user_id: int = STAFF_A, organization_id: int = ORG_A):
        return self._act_as(user_id, role="staff", organization_id=organization_id)

    def head(self, organization_id: int = ORG_A):
        return self._act_as(HEAD_A, role="institution_head", organization_id=organization_id)

    def super_admin(self):
        return self._act_as(SUPER, role="super_admin", organization_id=None)


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


async def open_ticket(client, *, category: str = "learning", subject: str = "I cannot follow lesson 3", key: str | None = None) -> dict[str, Any]:
    headers = {"Idempotency-Key": key} if key else {}
    response = await client.post("/api/v1/tickets", json={"subject": subject, "description": "Please explain the base case.", "category": category}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["ticket"]
