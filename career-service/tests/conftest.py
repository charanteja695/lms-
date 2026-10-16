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

from app.api.deps import _authenticate, get_gateway
from app.clients.gateway import GatewayClient
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.events.consumers.router import dispatch
from app.main import create_app
from app.models import Base

ORG_A, ORG_B = 1755000000050001, 1755000000050002
STUDENT, STUDENT_2 = 1755000000050101, 1755000000050102
STAFF_A, STAFF_B, MANAGER, SUPER = 1755000000050103, 1755000000050104, 1755000000050105, 1755000000050106
COURSE, COURSE_2 = 1755000000051001, 1755000000051002
CERT, CERT_2 = 1755000000052001, 1755000000052002
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
        "AI_GATEWAY_URL": "http://gateway.test",
        "PERCENTILE_MIN_COHORT": 3,
        "WORKER_POLL_SECONDS": 0.02,
    }
    values.update(overrides)
    return Settings(**values)


# What user-management puts in a token by default (its permission catalog), for the permissions this service checks.
ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {"student": ("career.profile",), "staff": ("career.students",), "institution_head": ("career.students",)}


def make_claims(*, user_id: int, role: str, organization_id: int | None, scopes: tuple[str, ...], defaults: bool = True) -> AccessTokenClaims:
    scopes = (*ROLE_PERMISSIONS.get(role, ()), *scopes) if defaults else scopes  # "defaults": the role's own
    now = datetime.now(UTC)
    return AccessTokenClaims(
        user_id=user_id, session_id=1755000000050002, role=role, organization_id=organization_id,
        organization_type="institution" if organization_id else None, scopes=scopes, token_version=0,
        token_id="test-token", issued_at=int(now.timestamp()), expires_at=now,
    )


class FakeGateway:
    """ai-gateway's completion API through httpx's mock transport. Script answers with ``reply(...)``; every request is recorded."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.replies: list[str] = []
        self.error: tuple[int, str] | None = None
        self.blocked = False

    def reply(self, text: str) -> None:
        self.replies.append(text)

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-Internal-Service-Token") == INTERNAL_TOKEN
        body = json.loads(request.content)
        self.requests.append(body)
        if self.error:
            return httpx.Response(self.error[0], json={"status": "error", "code": self.error[1]})
        status = "blocked" if self.blocked else "ok"
        text = "" if self.blocked else (self.replies.pop(0) if self.replies else "Built things.")
        completion = {"call_id": "1755000000099001", "status": status, "content": text, "model": "claude-sonnet-5", "provider": "anthropic", "guardrail_flags": []}
        return httpx.Response(200, json={"status": "success", "code": "SUCCESS", "message": "", "completion": completion})


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
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
async def app(db_engine, sessionmaker, settings, redis, gateway):
    fastapi_app = create_app(settings)
    fastapi_app.state.engine, fastapi_app.state.sessionmaker, fastapi_app.state.redis = db_engine, sessionmaker, redis
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    client = GatewayClient(settings, transport=httpx.MockTransport(gateway.handler))
    fastapi_app.dependency_overrides[get_gateway] = lambda: client
    yield fastapi_app


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


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

    def staff(self, user_id: int = STAFF_A, organization_id: int = ORG_A):
        return self._act_as(user_id, role="staff", organization_id=organization_id)

    def manager(self):
        return self._act_as(MANAGER, role="admin", organization_id=None, scopes=("careers.manage",))

    def other_admin(self):
        return self._act_as(SUPER + 1, role="admin", organization_id=None, scopes=("support.manage",))


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


def user_payload(user_id: int = STUDENT, *, first: str = "Asha", last: str = "Rao", org: int | None = ORG_A, role: str = "student", email: str | None = "asha@example.com") -> dict[str, Any]:
    return {"user_id": str(user_id), "email": email, "first_name": first, "last_name": last, "role": role, "status": "active", "organization_id": str(org) if org else None}


def certificate_payload(cert: int = CERT, course: int = COURSE, user: int = STUDENT) -> dict[str, Any]:
    return {
        "certificate_id": str(cert), "student_user_id": str(user), "organization_id": str(ORG_A), "course_id": str(course), "grade": "A", "score_percent": 91.5,
        "completion_date": "2026-08-30", "issued_at": "2026-09-01T10:00:00Z", "verification_url": f"https://lms.example/verify/{cert}",
    }


def attempt_payload(attempt: int, *, user: int = STUDENT, course: int = COURSE, percent: float = 80.0, result: str = "passed", kind: str = "final", revision: int = 1) -> dict[str, Any]:
    return {
        "attempt_id": str(attempt), "user_id": str(user), "course_id": str(course), "test_kind": kind, "result": result, "percent": percent, "revision": revision, "organization_id": str(ORG_A),
    }


async def seed_student(send_event, *, user: int = STUDENT, first: str = "Asha", last: str = "Rao", course_title: str = "Python Programming") -> None:
    await send_event("user.created", user_payload(user, first=first, last=last))
    await send_event("course.published", {"course_id": str(COURSE), "title": course_title})


SCHOOL = {"institution": "Anna University", "degree": "B.Tech", "field_of_study": "Computer Science", "start_date": "2022-08", "end_date": "2026-05", "grade": "8.4 CGPA"}
JOB = {
    "company": "Acme Labs", "title": "Software Intern", "location": "Chennai", "start_date": "2025-05", "end_date": "2025-07",
    "bullets": ["Built a REST API in Python that served 2000 requests per minute", "Fixed 14 bugs in the checkout flow", "worked on tests"],
}
PROJECT = {"name": "Library Manager", "url": "https://github.com/asha/library", "technologies": ["Python", "FastAPI", "PostgreSQL"], "description": "A web app to manage a college library."}


async def fill_profile(client) -> dict[str, str]:
    """Add one of each self-declared kind; returns the item ids by name."""
    ids: dict[str, str] = {}
    await client.patch("/api/v1/profile", json={"headline": "Aspiring backend developer", "phone": "+91 98765 43210", "location": "Chennai, India", "links": [{"label": "GitHub", "url": "https://github.com/asha"}]})
    for name, kind, data in (("edu", "education", SCHOOL), ("job", "experience", JOB), ("proj", "project", PROJECT), ("py", "skill", {"name": "Python"}), ("sql", "skill", {"name": "SQL"}), ("ach", "achievement", {"title": "Smart India Hackathon finalist", "date": "2025-03"})):
        response = await client.post("/api/v1/profile/items", json={"kind": kind, "data": data})
        assert response.status_code == 201, response.text
        ids[name] = response.json()["item"]["item_id"]
    return ids
