import json
import uuid
import zlib
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

from app.api.deps import _authenticate, get_gateway, get_support_client
from app.clients.gateway import GatewayClient
from app.clients.support import SupportClient
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.events.consumers.router import dispatch
from app.main import create_app
from app.models import Base
from app.rag.index_cache import IndexCache
from app.rag.similarity import tokenize

ORG_A, ORG_B = 1755000000020001, 1755000000020002
STUDENT, STUDENT_2 = 1755000000020101, 1755000000020102
AUTHOR, SUPPORT, STAFF_A, STAFF_B, SUPER = 1755000000020103, 1755000000020104, 1755000000020105, 1755000000020106, 1755000000020107
COURSE, VERSION = 1755000000021001, 1755000000021002
MODULE, TOPIC = 1755000000021003, 1755000000021004
NOTES_RECURSION, NOTES_LOOPS, PRACTICE_FIB, VIDEO_INTRO = 1755000000021101, 1755000000021102, 1755000000021103, 1755000000021104
MEDIA_INTRO = 1755000000021201
ENROLLMENT = 1755000000021301
INTERNAL_TOKEN = "test-internal-service-token-0123456789"
DIMS = 48

RECURSION_TEXT = (
    "Recursion is a technique where a function calls itself to solve a smaller version of the same problem. "
    "Every recursive function needs a base case that stops the recursion, and a recursive case that moves toward it."
)
LOOPS_TEXT = "A for loop repeats a block of code a fixed number of times. A while loop repeats as long as its condition stays true."
FIB_TEXT = "Write a function that returns the n-th Fibonacci number. Fibonacci numbers start with 0 and 1 and each next number is the sum of the previous two."


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
        "SUPPORT_SERVICE_URL": "http://support.test",
        "WORKER_POLL_SECONDS": 0.02,
        "EMBED_BATCH_SIZE": 4,
    }
    values.update(overrides)
    return Settings(**values)


# What user-management puts in a token by default (its permission catalog), for the permissions this service checks.
ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {"student": ("tutor.chat",), "staff": ("tutor.faq.manage", "tutor.conversations.view"), "institution_head": ("tutor.faq.manage", "tutor.conversations.view")}


def make_claims(*, user_id: int, role: str, organization_id: int | None, scopes: tuple[str, ...], defaults: bool = True) -> AccessTokenClaims:
    scopes = (*ROLE_PERMISSIONS.get(role, ()), *scopes) if defaults else scopes  # "defaults": the role's own
    now = datetime.now(UTC)
    return AccessTokenClaims(
        user_id=user_id, session_id=1755000000020002, role=role, organization_id=organization_id,
        organization_type="institution" if organization_id else None, scopes=scopes, token_version=0,
        token_id="test-token", issued_at=int(now.timestamp()), expires_at=now,
    )


def embed_text(text: str) -> list[float]:
    """A deterministic bag-of-words embedding: texts that share words are close, so retrieval is meaningful without a model."""
    vector = [0.0] * DIMS
    for token in tokenize(text):
        vector[zlib.crc32(token.encode()) % DIMS] += 1.0
    return vector


class FakeGateway:
    """ai-gateway's internal API, served through httpx's mock transport. Script completions with ``reply(...)``."""

    def __init__(self) -> None:
        self.completions: list[dict[str, Any]] = []
        self.embeddings: list[dict[str, Any]] = []
        self.replies: list[str] = []
        self.completion_error: tuple[int, str] | None = None
        self.embedding_error: tuple[int, str] | None = None
        self.blocked = False
        self.summary_error = False
        self.stream_error = False

    def reply(self, text: str) -> None:
        self.replies.append(text)

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-Internal-Service-Token") == INTERNAL_TOKEN
        body = json.loads(request.content)
        if request.url.path.endswith("/embeddings"):
            self.embeddings.append(body)
            if self.embedding_error:
                return httpx.Response(self.embedding_error[0], json={"status": "error", "code": self.embedding_error[1]})
            data = {"call_id": "1755000000099002", "vectors": [embed_text(t) for t in body["texts"]], "model": "voyage-3", "provider": "voyage", "tokens": 1, "cost_cents": 0}
            return httpx.Response(200, json={"status": "success", "code": "SUCCESS", "message": "", "embedding": data})
        self.completions.append(body)
        if body["prompt_key"].endswith("escalation_summary") and self.summary_error:
            return httpx.Response(502, json={"status": "error", "code": "PROVIDER_UNAVAILABLE"})
        if self.completion_error and not body["prompt_key"].endswith("escalation_summary"):
            return httpx.Response(self.completion_error[0], json={"status": "error", "code": self.completion_error[1]})
        if self.blocked:
            return httpx.Response(200, json=self._completion_body("", status="blocked", flags=["moderation"]))
        text = self.replies.pop(0) if self.replies else ("Summary for the agent." if body["prompt_key"].endswith("escalation_summary") else "Recursion means a function calls itself [1].")
        if body.get("stream"):
            lines = [{"type": "delta", "text": part} for part in (text[: len(text) // 2], text[len(text) // 2 :])]
            if self.stream_error:
                lines.append({"type": "error", "code": "PROVIDER_UNAVAILABLE", "message": "x"})
            else:
                lines.append({"type": "usage", "call_id": "1755000000099001", "provider": "anthropic", "model": "claude-sonnet-5", "prompt_tokens": 5, "completion_tokens": 5, "cost_cents": 0, "stop_reason": "end_turn"})
            return httpx.Response(200, content=("\n".join(json.dumps(line) for line in lines) + "\n").encode(), headers={"content-type": "application/x-ndjson"})
        return httpx.Response(200, json=self._completion_body(text))

    @staticmethod
    def _completion_body(text: str, *, status: str = "ok", flags: list[str] | None = None) -> dict[str, Any]:
        completion = {
            "call_id": "1755000000099001", "status": status, "content": text, "model": "claude-sonnet-5", "provider": "anthropic", "prompt_tokens": 5,
            "completion_tokens": 5, "cost_cents": 0, "guardrail_flags": flags or [], "stop_reason": "end_turn",
        }
        return {"status": "success", "code": "SUCCESS", "message": "", "completion": completion}

    def tutor_calls(self) -> list[dict[str, Any]]:
        return [c for c in self.completions if not c["prompt_key"].endswith("escalation_summary")]


class FakeSupport:
    """support-service's internal ticket API."""

    def __init__(self) -> None:
        self.tickets: list[dict[str, Any]] = []
        self.keys: dict[str, int] = {}
        self.fail_with: int | None = None
        self.calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-Internal-Service-Token") == INTERNAL_TOKEN
        self.calls += 1
        if self.fail_with is not None:
            return httpx.Response(self.fail_with, json={"status": "error", "message": "no"})
        key = request.headers["Idempotency-Key"]
        if key not in self.keys:
            self.tickets.append(json.loads(request.content))
            self.keys[key] = 1755000000030000 + len(self.tickets)
        return httpx.Response(201, json={"status": "success", "ticket": {"ticket_id": str(self.keys[key])}})


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
def support() -> FakeSupport:
    return FakeSupport()


@pytest.fixture
def gateway_client(settings, gateway) -> GatewayClient:
    return GatewayClient(settings, transport=httpx.MockTransport(gateway.handler))


@pytest.fixture
def support_client(settings, support) -> SupportClient:
    return SupportClient(settings, transport=httpx.MockTransport(support.handler))


@pytest.fixture
async def app(db_engine, sessionmaker, settings, redis, gateway_client, support_client):
    fastapi_app = create_app(settings)
    fastapi_app.state.engine, fastapi_app.state.sessionmaker, fastapi_app.state.redis = db_engine, sessionmaker, redis
    fastapi_app.state.index_cache = IndexCache(settings.INDEX_CACHE_VERSIONS)
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    fastapi_app.dependency_overrides[get_gateway] = lambda: gateway_client
    fastapi_app.dependency_overrides[get_support_client] = lambda: support_client
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

    def author(self):
        return self._act_as(AUTHOR, role="admin", organization_id=None, scopes=("content.author",))

    def support_manager(self):
        return self._act_as(SUPPORT, role="admin", organization_id=None, scopes=("support.manage",))

    def ai_manager(self):
        return self._act_as(SUPPORT, role="admin", organization_id=None, scopes=("ai.manage",))

    def staff(self, user_id: int = STAFF_A, organization_id: int = ORG_A):
        return self._act_as(user_id, role="staff", organization_id=organization_id)

    def super_admin(self):
        return self._act_as(SUPER, role="super_admin", organization_id=None)


@pytest.fixture
def who(act_as) -> Identities:
    return Identities(act_as)


def published_payload(*, version: int = VERSION, course: int = COURSE, with_video: bool = False) -> dict[str, Any]:
    items = [
        {"topic_item_id": str(NOTES_RECURSION), "title": "Recursion basics", "position": 1, "item_type": "notes", "required": True, "media_id": None, "duration_seconds": None, "content_text": RECURSION_TEXT},
        {"topic_item_id": str(NOTES_LOOPS), "title": "Loops", "position": 2, "item_type": "notes", "required": True, "media_id": None, "duration_seconds": None, "content_text": LOOPS_TEXT},
        {"topic_item_id": str(PRACTICE_FIB), "title": "Fibonacci", "position": 3, "item_type": "practice", "required": True, "media_id": None, "duration_seconds": None, "content_text": FIB_TEXT},
    ]
    if with_video:
        items.append({"topic_item_id": str(VIDEO_INTRO), "title": "Intro video", "position": 4, "item_type": "video", "required": True, "media_id": str(MEDIA_INTRO), "duration_seconds": 600, "content_text": None})
    return {
        "course_id": str(course), "version_id": str(version), "title": "Python Foundations", "slug": "python-foundations", "unlock_mode": "sequential",
        "modules": [{"module_id": str(MODULE), "title": "Basics", "position": 1, "pass_mark": 60, "module_test_id": None, "topics": [{"topic_id": str(TOPIC), "title": "Functions", "position": 1, "pass_mark": 60, "topic_test_id": None, "items": items}]}],
    }


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
def index_now(sessionmaker, settings, gateway_client) -> Callable[..., Any]:
    """Run the worker's embedding sweep once."""

    async def _run() -> int:
        from app.services.index_service import index_due

        return await index_due(sessionmaker, settings, gateway_client)

    return _run


@pytest.fixture
def deliver_now(sessionmaker, settings, gateway_client, support_client) -> Callable[..., Any]:
    async def _run() -> int:
        from app.services.escalation_service import deliver_due

        return await deliver_due(sessionmaker, settings, gateway_client, support_client)

    return _run


@pytest.fixture
async def course(send_event, index_now):
    """A published, indexed course the student is enrolled in."""
    await send_event("course.published", published_payload())
    await index_now()
    await send_event("enrollment.created", {"enrollment_id": str(ENROLLMENT), "student_user_id": str(STUDENT), "organization_id": str(ORG_A), "version_id": str(VERSION), "batch_id": "1"})


async def start_conversation(client, *, mode: str = "learning", course_id: int | None = COURSE) -> str:
    body: dict[str, Any] = {"mode": mode}
    if course_id is not None:
        body["course_id"] = str(course_id)
    response = await client.post("/api/v1/conversations", json=body)
    assert response.status_code == 201, response.text
    return response.json()["conversation"]["conversation_id"]


async def ask(client, conversation_id: str, content: str, *, key: str | None = None, context: dict[str, Any] | None = None, stream: bool = False):
    headers = {"Idempotency-Key": key} if key else {}
    body: dict[str, Any] = {"content": content, "stream": stream}
    if context:
        body["context"] = context
    return await client.post(f"/api/v1/conversations/{conversation_id}/messages", json=body, headers=headers)
