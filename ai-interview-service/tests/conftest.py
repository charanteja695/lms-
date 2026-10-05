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

from app.api.deps import _authenticate, get_codeexec, get_gateway
from app.clients.codeexec import CodeExecutionClient
from app.clients.gateway import GatewayClient
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.events.consumers.router import dispatch
from app.main import create_app
from app.models import Base
from app.worker.work import run_due

STUDENT, STUDENT_2 = 1755000000080101, 1755000000080102
RECRUITER, EMP_ADMIN, RECRUITER_2 = 1755000000080111, 1755000000080112, 1755000000080113
MANAGER, OTHER_ADMIN = 1755000000080131, 1755000000080132
EMPLOYER, EMPLOYER_2, INSTITUTION = 1755000000080011, 1755000000080012, 1755000000080021
INTERNAL_TOKEN = "test-internal-service-token-0123456789"
API = "/api/v1"


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "ENVIRONMENT": "test", "DATABASE_URL": "sqlite+aiosqlite:///:memory:", "REDIS_URL": "redis://localhost:6379/15", "DOCS_ENABLED": False, "RATE_LIMIT_ENABLED": False,
        "LOG_JSON": False, "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN, "AI_GATEWAY_URL": "http://gateway.test", "CODE_EXECUTION_URL": "http://codeexec.test",
        "WORKER_POLL_SECONDS": 0.02, "START_GRACE_MINUTES": 15, "OVERRUN_GRACE_SECONDS": 2, "APPEAL_WINDOW_DAYS": 7,
    }
    values.update(overrides)
    return Settings(**values)


def make_claims(*, user_id: int, role: str, organization_id: int | None, scopes: tuple[str, ...] = ()) -> AccessTokenClaims:
    now = datetime.now(UTC)
    return AccessTokenClaims(
        user_id=user_id, session_id=1755000000080002, role=role, organization_id=organization_id, organization_type="employer" if role in {"recruiter", "employer_admin"} else None,
        scopes=scopes, token_version=0, token_id="test-token", issued_at=int(now.timestamp()), expires_at=now,
    )


# ---------------------------------------------------------------- fakes of the services this one calls
class FakeGateway:
    """ai-gateway: chat completions (scripted replies), and speech-to-text / text-to-speech (contract only)."""

    def __init__(self) -> None:
        self.completions: list[dict[str, Any]] = []
        self.replies: list[str] = []
        self.completion_error: tuple[int, str] | None = None
        self.blocked = False
        self.stt_available = True
        self.tts_available = True
        self.transcriptions: list[bytes] = []
        self.speeches: list[str] = []

    def reply(self, text: str) -> None:
        self.replies.append(text)

    def reply_follow_up(self, follow_up: str | None) -> None:
        self.replies.append(json.dumps({"follow_up": follow_up}))

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-Internal-Service-Token") == INTERNAL_TOKEN
        path = request.url.path
        if path.endswith("/transcriptions"):
            self.transcriptions.append(request.content)
            if not self.stt_available:
                return httpx.Response(503, json={"status": "error", "code": "PROVIDER_NOT_CONFIGURED"})
            return httpx.Response(200, json={"status": "success", "code": "SUCCESS", "message": "", "transcription": {"text": "This is my spoken answer."}})
        if path.endswith("/speech"):
            body = json.loads(request.content)
            self.speeches.append(body["text"])
            if not self.tts_available:
                return httpx.Response(503, json={"status": "error", "code": "PROVIDER_NOT_CONFIGURED"})
            return httpx.Response(200, content=b"\x00\x01fake-audio", headers={"content-type": "audio/mpeg"})
        body = json.loads(request.content)
        self.completions.append(body)
        if self.completion_error:
            return httpx.Response(self.completion_error[0], json={"status": "error", "code": self.completion_error[1]})
        status = "blocked" if self.blocked else "ok"
        text = "" if self.blocked else (self.replies.pop(0) if self.replies else json.dumps({"follow_up": None}))
        completion = {"call_id": "1755000000099001", "status": status, "content": text, "model": "claude-sonnet-5", "provider": "anthropic", "guardrail_flags": [], "prompt_version": 3}
        return httpx.Response(200, json={"status": "success", "code": "SUCCESS", "message": "", "completion": completion})


class FakeCodeExec:
    """code-execution-service's internal run endpoints (queue then poll)."""

    def __init__(self) -> None:
        self.runs: list[dict[str, Any]] = []
        self.down = False
        self.outcome = "passed"
        self.stdout = "hello\n"
        self._next_id = 1755000000099500

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-Internal-Service-Token") == INTERNAL_TOKEN
        if self.down:
            return httpx.Response(503, json={"status": "error", "code": "UNAVAILABLE"})
        if request.method == "POST":
            body = json.loads(request.content)
            self.runs.append(body)
            self._next_id += 1
            return httpx.Response(202, json={"status": "success", "code": "SUCCESS", "message": "", "run": {"run_id": str(self._next_id)}})
        run = {"run_id": str(self._next_id), "status": "completed", "outcome": self.outcome, "stdout": self.stdout, "stderr": "", "compile_output": "", "time_ms": 42}
        return httpx.Response(200, json={"status": "success", "code": "SUCCESS", "message": "", "run": run})


# ---------------------------------------------------------------- fixtures
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
def codeexec() -> FakeCodeExec:
    return FakeCodeExec()


@pytest.fixture
def clients(settings, gateway, codeexec) -> tuple[GatewayClient, CodeExecutionClient]:
    return (GatewayClient(settings, transport=httpx.MockTransport(gateway.handler)), CodeExecutionClient(settings, transport=httpx.MockTransport(codeexec.handler)))


@pytest.fixture
async def app(db_engine, sessionmaker, settings, redis, clients):
    fastapi_app = create_app(settings)
    fastapi_app.state.engine, fastapi_app.state.sessionmaker, fastapi_app.state.redis = db_engine, sessionmaker, redis
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    fastapi_app.dependency_overrides[get_gateway] = lambda: clients[0]
    fastapi_app.dependency_overrides[get_codeexec] = lambda: clients[1]
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

    def student(self, user_id: int = STUDENT, organization_id: int | None = INSTITUTION):
        return self._act_as(user_id, role="student", organization_id=organization_id)

    def recruiter(self, user_id: int = RECRUITER, organization_id: int = EMPLOYER):
        return self._act_as(user_id, role="recruiter", organization_id=organization_id)

    def employer_admin(self, user_id: int = EMP_ADMIN, organization_id: int = EMPLOYER):
        return self._act_as(user_id, role="employer_admin", organization_id=organization_id)

    def manager(self, user_id: int = MANAGER):
        return self._act_as(user_id, role="admin", organization_id=None, scopes=("careers.manage",))

    def other_admin(self):
        return self._act_as(OTHER_ADMIN, role="admin", organization_id=None, scopes=("support.manage",))


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


@pytest.fixture
def work(sessionmaker, settings, clients) -> Callable[..., Any]:
    """Run the worker's queue until it is empty, like the worker loop would."""

    async def _run(limit: int = 50) -> int:
        total = 0
        for _ in range(limit):
            done = await run_due(sessionmaker, settings, clients[0])
            if not done:
                break
            total += done
        return total

    return _run


# ---------------------------------------------------------------- plan / interview helpers
def round_body(*, type_: str = "technical", minutes: int = 10, questions: tuple[str, ...] = ("Tell me about a project you are proud of.",), languages: tuple[str, ...] = (), criteria: tuple[str, ...] = ()) -> dict[str, Any]:
    body: dict[str, Any] = {"type": type_, "minutes": minutes, "questions": list(questions)}
    if languages:
        body["languages"] = list(languages)
    if criteria:
        body["criteria"] = list(criteria)
    return body


def plan_body(*, kind: str = "mock", rounds: list[dict[str, Any]] | None = None, duration_minutes: int = 20, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "kind": kind, "title": "Backend Engineer Interview", "role": "Backend Engineer", "skills": ["Python"], "difficulty": "medium", "duration_minutes": duration_minutes,
        "rounds": rounds or [round_body(type_="intro", minutes=5, questions=("Tell me about yourself.",)), round_body(type_="technical", minutes=15)],
    }
    body.update(overrides)
    return body


async def create_published_plan(client: AsyncClient, who: Identities, *, kind: str = "mock", **overrides: Any) -> str:
    if kind == "mock":
        who.manager()
    else:
        who.recruiter()
    created = await client.post(f"{API}/interview-plans", json=plan_body(kind=kind, **overrides))
    assert created.status_code == 201, created.text
    plan_id = created.json()["plan"]["plan_id"]
    published = await client.post(f"{API}/interview-plans/{plan_id}/publish")
    assert published.status_code == 200, published.text
    return plan_id
