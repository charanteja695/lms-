import json
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import boto3
import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from lms_common.auth import AccessTokenClaims
from lms_common.events import Event
from moto import mock_aws
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.api.deps import _authenticate
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.events.consumers.router import dispatch
from app.main import create_app
from app.models import Base

ORG_A, ORG_B = 1755000000007003, 1755000000007004
STUDENT, STUDENT_2 = 1755000000007101, 1755000000007102
AUTHOR, REVIEWER, EXAM_MANAGER = 1755000000007103, 1755000000007104, 1755000000007106
SUPER_ADMIN, STAFF_A, STAFF_B = 1755000000007105, 1755000000007108, 1755000000007109
COURSE, VERSION, ENROLLMENT = 1755000000008001, 1755000000008002, 1755000000008005
ATTEMPT = 1755000000009001


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "ENVIRONMENT": "test",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "REDIS_URL": "redis://localhost:6379/15",
        "DOCS_ENABLED": False,
        "RATE_LIMIT_ENABLED": False,
        "LOG_JSON": False,
        "WORKER_POLL_SECONDS": 0.02,
        "S3_BUCKET": "lms-certificates-test",
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "PUBLIC_VERIFY_BASE_URL": "https://lms.example/verify",
    }
    values.update(overrides)
    return Settings(**values)


# What user-management puts in a token by default (its permission catalog), for the permissions this service checks.
ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {"student": ("certificates.own",), "staff": ("certificates.students",), "institution_head": ("certificates.students",)}


def make_claims(*, user_id: int, role: str, organization_id: int | None, scopes: tuple[str, ...], defaults: bool = True) -> AccessTokenClaims:
    scopes = (*ROLE_PERMISSIONS.get(role, ()), *scopes) if defaults else scopes  # "defaults": the role's own
    now = datetime.now(UTC)
    return AccessTokenClaims(
        user_id=user_id, session_id=1755000000007002, role=role, organization_id=organization_id,
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
async def app(db_engine, sessionmaker, settings, redis):
    fastapi_app = create_app(settings)
    fastapi_app.state.engine, fastapi_app.state.sessionmaker, fastapi_app.state.redis = db_engine, sessionmaker, redis
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    yield fastapi_app


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


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

    def student(self, user_id: int = STUDENT, organization_id: int = ORG_A):
        return self._act_as(user_id, role="student", organization_id=organization_id)

    def author(self):
        return self._act_as(AUTHOR, role="admin", organization_id=None, scopes=("content.author",))

    def reviewer(self):
        return self._act_as(REVIEWER, role="admin", organization_id=None, scopes=("content.review",))

    def exam_manager(self):
        return self._act_as(EXAM_MANAGER, role="admin", organization_id=None, scopes=("exams.manage",))

    def super_admin(self):
        return self._act_as(SUPER_ADMIN, role="super_admin", organization_id=None)

    def staff(self, user_id: int = STAFF_A, organization_id: int = ORG_A):
        return self._act_as(user_id, role="staff", organization_id=organization_id)


@pytest.fixture
def who(act_as) -> Identities:
    return Identities(act_as)


@pytest.fixture
def send_event(sessionmaker, settings) -> Callable[..., Any]:
    """Deliver an event the way the worker's consumer does: through the router, in one transaction."""

    async def _send(event_type: str, payload: dict[str, Any], *, event_id: str | None = None) -> None:
        event = Event(event_id=event_id or uuid.uuid4().hex, event_type=event_type, aggregate_type="x",
                      occurred_time=datetime.now(UTC), payload=json.loads(json.dumps(payload)))
        async with sessionmaker() as db:
            await dispatch(db, event, settings)
            await db.commit()

    return _send


@pytest.fixture
def directory(send_event) -> Callable[..., Any]:
    """The names a certificate prints, as user-management and catalog-service would announce them."""

    async def _seed(*, student: int = STUDENT, first: str = "Aarav", last: str = "Reddy", org: int = ORG_A) -> None:
        await send_event("institution.created", {"organization_id": str(org), "name": "Springfield High", "organization_type": "institution"})
        await send_event("user.created", {"user_id": str(student), "first_name": first, "last_name": last, "role": "student", "organization_id": str(org)})
        await send_event("course.published", {"course_id": str(COURSE), "version_id": str(VERSION), "title": "Full Stack Development with MERN"})

    return _seed


def passed_payload(*, student: int = STUDENT, attempt: int = ATTEMPT, org: int = ORG_A, percent: float = 91.5) -> dict[str, Any]:
    """Assessment-service's ``course.passed`` payload (see its ResultService._course_events)."""
    return {
        "course_id": str(COURSE), "version_id": str(VERSION), "enrollment_id": str(ENROLLMENT), "student_user_id": str(student),
        "organization_id": str(org), "test_id": "1755000000000555", "attempt_id": str(attempt), "score": 91.5, "max_score": 100.0,
        "percent": percent, "best_percent": percent, "pass_mark_percent": 60, "attempt_no": 1, "passed_at": "2026-09-21T10:30:00Z",
    }


@pytest.fixture
def s3_bucket(settings):
    with mock_aws():
        client = boto3.client("s3", region_name=settings.AWS_REGION, aws_access_key_id="testing", aws_secret_access_key="testing")
        client.create_bucket(Bucket=settings.S3_BUCKET, CreateBucketConfiguration={"LocationConstraint": settings.AWS_REGION})
        yield client


@pytest.fixture
def render(sessionmaker, settings, s3_bucket) -> Callable[..., Any]:
    """Run the worker's PDF sweep once."""

    async def _render() -> int:
        from app.services.pdf_service import generate_due

        return await generate_due(sessionmaker, settings)

    return _render
