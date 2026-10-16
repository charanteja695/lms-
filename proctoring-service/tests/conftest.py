import json
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import boto3
import fakeredis.aioredis
import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from lms_common.auth import AccessTokenClaims
from lms_common.events import Event
from moto import mock_aws
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.api.deps import _authenticate
from app.clients.analyzer import AnalyzerClient
from app.clients.assessment import AssessmentClient
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.events.consumers.router import dispatch
from app.main import create_app
from app.models import Base
from app.models.outbox_event import OutboxEvent

ORG_A, ORG_B, EMPLOYER = 1755000000007003, 1755000000007004, 1755000000007005
STUDENT, STUDENT_2 = 1755000000007101, 1755000000007102
EXAM_MANAGER, EXAM_MANAGER_2, SUPER_ADMIN = 1755000000007106, 1755000000007113, 1755000000007105
STAFF_A, STAFF_B, RECRUITER = 1755000000007108, 1755000000007109, 1755000000007110
TEST_BASIC, TEST_STRICT, TEST_HIRING = 1755000000000555, 1755000000000556, 1755000000000557
ATTEMPT = 1755000000009001
INTERNAL_TOKEN = "test-internal-service-token"


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "ENVIRONMENT": "test", "DATABASE_URL": "sqlite+aiosqlite:///:memory:", "REDIS_URL": "redis://localhost:6379/15",
        "DOCS_ENABLED": False, "RATE_LIMIT_ENABLED": False, "LOG_JSON": False, "WORKER_POLL_SECONDS": 0.02,
        "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN, "S3_BUCKET": "lms-proctoring-test", "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing", "ASSESSMENT_SERVICE_URL": "http://assessment.test",
        "ANALYSIS_WAIT_SECONDS": 0, "CLIENT_CLOCK_SKEW_SECONDS": 300,
    }
    values.update(overrides)
    return Settings(**values)


# What user-management puts in a token by default (its permission catalog), for the permissions this service checks.
ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {"student": ("proctoring.take",), "staff": ("proctoring.monitor",), "institution_head": ("proctoring.monitor",), "employer_admin": ("proctoring.monitor",), "recruiter": ("proctoring.monitor",)}


def make_claims(*, user_id: int, role: str, organization_id: int | None, scopes: tuple[str, ...], defaults: bool = True) -> AccessTokenClaims:
    scopes = (*ROLE_PERMISSIONS.get(role, ()), *scopes) if defaults else scopes  # "defaults": the role's own
    now = datetime.now(UTC)
    return AccessTokenClaims(
        user_id=user_id, session_id=1755000000007002, role=role, organization_id=organization_id,
        organization_type="employer" if organization_id == EMPLOYER else ("institution" if organization_id else None), scopes=scopes,
        token_version=0, token_id="test-token", issued_at=int(now.timestamp()), expires_at=now,
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


class FakeAssessment:
    """assessment-service's internal API, served through httpx's mock transport."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.fail_with: int | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-Internal-Service-Token") == INTERNAL_TOKEN
        action = request.url.path.rsplit("/", 1)[-1]
        attempt = request.url.path.split("/")[-2]
        self.calls.append((action, {"attempt_id": attempt, **json.loads(request.content or b"{}")}))
        if self.fail_with is not None:
            return httpx.Response(self.fail_with, json={"status": "error", "message": "no"})
        return httpx.Response(200, json={"status": "success"})


@pytest.fixture
def assessment() -> FakeAssessment:
    return FakeAssessment()


class FakeAnalyzer:
    """An AI analysis worker: answers each snapshot with the findings the test scripted for it (default: nothing found)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.findings: list[dict[str, Any]] = []
        self.fail_with: int | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(json.loads(request.content))
        if self.fail_with is not None:
            return httpx.Response(self.fail_with, json={})
        return httpx.Response(200, json={"findings": self.findings})


@pytest.fixture
def analyzer_service() -> FakeAnalyzer:
    return FakeAnalyzer()


@pytest.fixture
async def app(db_engine, sessionmaker, settings, redis, assessment, monkeypatch):
    fastapi_app = create_app(settings)
    fastapi_app.state.engine, fastapi_app.state.sessionmaker, fastapi_app.state.redis = db_engine, sessionmaker, redis
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    real_init = AssessmentClient.__init__

    def init(self, settings, transport=None):  # every AssessmentClient the app builds talks to the fake
        real_init(self, settings, transport=httpx.MockTransport(assessment.handler))

    monkeypatch.setattr(AssessmentClient, "__init__", init)
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

    def exam_manager(self, user_id: int = EXAM_MANAGER):
        return self._act_as(user_id, role="admin", organization_id=None, scopes=("exams.manage",))

    def staff(self, user_id: int = STAFF_A, organization_id: int = ORG_A):
        return self._act_as(user_id, role="staff", organization_id=organization_id)

    def recruiter(self, organization_id: int = EMPLOYER):
        return self._act_as(RECRUITER, role="recruiter", organization_id=organization_id)


@pytest.fixture
def who(act_as) -> Identities:
    return Identities(act_as)


@pytest.fixture
def send_event(sessionmaker, settings, redis) -> Callable[..., Any]:
    async def _send(event_type: str, payload: dict[str, Any], *, event_id: str | None = None) -> None:
        event = Event(event_id=event_id or uuid.uuid4().hex, event_type=event_type, aggregate_type="x", occurred_time=datetime.now(UTC), payload=json.loads(json.dumps(payload)))
        async with sessionmaker() as db:
            await dispatch(db, event, settings, redis)
            await db.commit()

    return _send


@pytest.fixture
def tests_published(send_event):
    """assessment-service announces a basic, a strict and an employer's hiring test."""

    async def _publish() -> None:
        for test_id, level, owner in ((TEST_BASIC, "basic", None), (TEST_STRICT, "strict", None), (TEST_HIRING, "strict", str(EMPLOYER))):
            await send_event("test.published", {"test_id": str(test_id), "title": f"Test {test_id}", "kind": "final" if owner is None else "hiring", "proctoring_level": level, "organization_id": owner})
        await send_event("test.published", {"test_id": "1755000000000599", "title": "Open book", "kind": "practice", "proctoring_level": "none", "organization_id": None})

    return _publish


def started_payload(*, test_id: int = TEST_BASIC, level: str = "basic", user: int = STUDENT, attempt: int = ATTEMPT, org: int | None = ORG_A) -> dict[str, Any]:
    """assessment-service's ``attempt.started`` payload (see its attempt_event_payload)."""
    return {"attempt_id": str(attempt), "test_id": str(test_id), "test_kind": "final", "user_id": str(user), "organization_id": str(org) if org else None, "proctoring_level": level, "attempt_no": 1}


@pytest.fixture
def s3_bucket(settings):
    with mock_aws():
        client = boto3.client("s3", region_name=settings.AWS_REGION, aws_access_key_id="testing", aws_secret_access_key="testing")
        client.create_bucket(Bucket=settings.S3_BUCKET, CreateBucketConfiguration={"LocationConstraint": settings.AWS_REGION})
        yield client


async def outbox(sessionmaker, event_type: str) -> list[dict]:
    async with sessionmaker() as db:
        rows = (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == event_type).order_by(OutboxEvent.created_at))).scalars()
        return [row.payload for row in rows]


class Work:
    """The worker's loops, one step at a time."""

    def __init__(self, sessionmaker, settings, redis, analyzer_service) -> None:
        self.sessionmaker, self.settings, self.redis, self.analyzer_service = sessionmaker, settings, redis, analyzer_service

    def _analyzer(self) -> AnalyzerClient:
        return AnalyzerClient(self.settings, transport=httpx.MockTransport(self.analyzer_service.handler))

    async def analyze(self) -> int:
        from app.services.snapshot_service import analyze_due

        return await analyze_due(self.sessionmaker, self.settings, self._analyzer())

    async def finalize(self) -> int:
        from app.services.case_service import finalize_sweep

        return await finalize_sweep(self.sessionmaker, self.settings)

    async def heartbeats(self) -> int:
        from app.worker.runner import sweep_heartbeats

        return await sweep_heartbeats(self.sessionmaker, self.redis, self.settings)

    async def housekeeping(self) -> None:
        from app.worker.runner import housekeeping

        await housekeeping(self.sessionmaker, self.redis, self.settings)


@pytest.fixture
def work(sessionmaker, settings, redis, analyzer_service) -> Work:
    return Work(sessionmaker, settings, redis, analyzer_service)
