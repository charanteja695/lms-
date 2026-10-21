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

from app.api.deps import _authenticate
from app.clients.code_execution import CodeExecutionClient
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.events.consumers.router import dispatch
from app.main import create_app
from app.models import Base

TEST_SESSION_ID = 1755000000007002
ORG_A = 1755000000007003
ORG_B = 1755000000007004
EMPLOYER = 1755000000007005
EMPLOYER_2 = 1755000000007006
STUDENT = 1755000000007101
STUDENT_2 = 1755000000007102
STUDENT_B = 1755000000007107
AUTHOR = 1755000000007103
REVIEWER = 1755000000007104
SUPER_ADMIN = 1755000000007105
EXAM_MANAGER = 1755000000007106
STAFF_A = 1755000000007108
STAFF_B = 1755000000007109
RECRUITER = 1755000000007110
EMPLOYER_ADMIN = 1755000000007111
EMPLOYER_ADMIN_2 = 1755000000007112
INTERNAL_TOKEN = "test-internal-service-token"

COURSE = 1755000000008001
VERSION = 1755000000008002
MODULE = 1755000000008003
TOPIC = 1755000000008004
ENROLLMENT = 1755000000008005
ENROLLMENT_2 = 1755000000008006


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
        "S3_BUCKET": "lms-assessment-test",
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "POOL_CACHE_SECONDS": 0,
        "PROCTORING_PRECHECK_REQUIRED": False,  # most tests are not about proctoring; tests/integration/test_proctoring_gate.py is
        # most tests publish tiny papers; tests/integration/test_course_test_composition.py covers these rules
        "TOPIC_TEST_MIN_MCQ": 0,
        "TOPIC_TEST_MIN_PROGRAMS": 0,
        "FINAL_TEST_MIN_MCQ": 0,
        "FINAL_TEST_MIN_PROGRAMS": 0,
        "CODE_EXECUTION_URL": "http://code-execution.test",
    }
    values.update(overrides)
    return Settings(**values)


# What user-management puts in a token by default (its permission catalog), for the permissions this service checks.
# What user-management's token carries by default: matrix cells plus the feature keys they imply (company roles: keys only).
ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {"student": ("my_tests.view", "assessments.take"), "staff": ("attempts.view", "attempts.update", "assessments.grade"), "institution_head": ("attempts.view", "attempts.update", "assessments.grade"), "employer_admin": ("assessments.author", "assessments.review", "assessments.manage"), "recruiter": ("assessments.author", "assessments.manage")}


def make_claims(*, user_id: int, role: str, organization_id: int | None, scopes: tuple[str, ...], defaults: bool = True) -> AccessTokenClaims:
    scopes = (*ROLE_PERMISSIONS.get(role, ()), *scopes) if defaults else scopes  # "defaults": the role's own
    now = datetime.now(UTC)
    return AccessTokenClaims(
        user_id=user_id,
        session_id=TEST_SESSION_ID,
        role=role,
        organization_id=organization_id,
        organization_type=None if organization_id is None else ("employer" if organization_id in (EMPLOYER, EMPLOYER_2) else "institution"),
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
async def app(db_engine: AsyncEngine, sessionmaker: async_sessionmaker, settings: Settings, redis):
    fastapi_app = create_app(settings)
    fastapi_app.state.engine = db_engine
    fastapi_app.state.sessionmaker = sessionmaker
    fastapi_app.state.redis = redis
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    yield fastapi_app


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def act_as(app) -> Callable[..., AccessTokenClaims]:
    """Sign the test client in as someone. Roles/scopes are exactly what user-management would put in a token."""

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

    def recruiter(self, user_id: int = RECRUITER, organization_id: int = EMPLOYER):
        return self._act_as(user_id, role="recruiter", organization_id=organization_id)

    def employer_admin(self, user_id: int = EMPLOYER_ADMIN, organization_id: int = EMPLOYER):
        return self._act_as(user_id, role="employer_admin", organization_id=organization_id)


@pytest.fixture
def who(act_as) -> Identities:
    return Identities(act_as)


# ----------------------------------------------------------------------------- events


@pytest.fixture
def send_event(sessionmaker: async_sessionmaker, settings: Settings, redis) -> Callable[..., Any]:
    """Deliver an event the way the worker's inbound consumer does: through the router, in one transaction."""

    async def _send(event_type: str, payload: dict[str, Any], *, event_id: str | None = None) -> None:
        event = Event(
            event_id=event_id or uuid.uuid4().hex,
            event_type=event_type,
            aggregate_type="test",
            occurred_time=datetime.now(UTC),
            payload=json.loads(json.dumps(payload)),
        )
        async with sessionmaker() as db:
            await dispatch(db, event, settings, redis)
            await db.commit()

    return _send


@pytest.fixture
def enroll(send_event) -> Callable[..., Any]:
    """Enrol a student in the fixture course version and (optionally) mark them eligible for the final test."""

    async def _enroll(
        student: int = STUDENT,
        *,
        enrollment_id: int = ENROLLMENT,
        organization_id: int = ORG_A,
        eligible: bool = False,
        topic_test_id: int | None = None,
        module_test_id: int | None = None,
        version_id: int = VERSION,
        course_id: int = COURSE,
        module_id: int = MODULE,
        topic_id: int = TOPIC,
    ) -> None:
        await send_event(
            "course.published",
            {
                "course_id": str(course_id),
                "version_id": str(version_id),
                "title": "Course",
                "slug": "course",
                "final_test_id": None,
                "modules": [
                    {
                        "module_id": str(module_id),
                        "module_test_id": str(module_test_id) if module_test_id else None,
                        "topics": [{"topic_id": str(topic_id), "topic_test_id": str(topic_test_id) if topic_test_id else None, "items": []}],
                    }
                ],
            },
        )
        await send_event(
            "enrollment.created",
            {
                "enrollment_id": str(enrollment_id),
                "student_user_id": str(student),
                "organization_id": str(organization_id),
                "version_id": str(version_id),
            },
        )
        if eligible:
            await send_event(
                "course.eligible_for_final",
                {"enrollment_id": str(enrollment_id), "version_id": str(version_id), "student_user_id": str(student)},
            )

    return _enroll


# ----------------------------------------------------------------------------- factories


def mcq(correct: str = "b", *, text: str = "Pick the second option", **fields: Any) -> dict[str, Any]:
    return {
        "question_type": "mcq_single",
        "text": text,
        "body": {"options": [{"id": "a", "text": "First"}, {"id": "b", "text": "Second"}, {"id": "c", "text": "Third"}]},
        "answer_key": {"correct": correct},
        **fields,
    }


def true_false(correct: bool = True, **fields: Any) -> dict[str, Any]:
    return {"question_type": "true_false", "text": "The sky is blue.", "body": {}, "answer_key": {"correct": correct}, **fields}


def subjective(**fields: Any) -> dict[str, Any]:
    body = {"rubric": [{"id": "clarity", "criterion": "Clarity", "max_marks": 4}, {"id": "depth", "criterion": "Depth", "max_marks": 6}]}
    return {"question_type": "subjective", "text": "Explain recursion.", "body": body, "answer_key": {}, **fields}


def coding(problem_id: str = "1755000000006555", **fields: Any) -> dict[str, Any]:
    return {"question_type": "coding", "text": "Add two numbers.", "body": {"problem_id": problem_id, "languages": ["python"]}, "answer_key": {}, **fields}


@pytest.fixture
def make_question(client: AsyncClient, who: Identities) -> Callable[..., Any]:
    """Author a question, have it reviewed and published, through the API. Returns its public id."""

    async def _make(payload: dict[str, Any] | None = None, *, publish: bool = True, **overrides: Any) -> str:
        body = {**(payload or mcq()), **overrides}
        who.author()
        created = await client.post("/api/v1/questions", json=body)
        assert created.status_code == 201, created.text
        question_id = created.json()["question"]["question_id"]
        if publish:
            assert (await client.post(f"/api/v1/questions/{question_id}/submit")).status_code == 200
            who.reviewer()
            approved = await client.post(f"/api/v1/questions/{question_id}/approve", json={})
            assert approved.status_code == 200, approved.text
        return str(question_id)

    return _make


def fixed(question_id: str, marks: float | None = None) -> dict[str, Any]:
    slot: dict[str, Any] = {"slot_type": "fixed", "question_id": question_id}
    if marks is not None:
        slot["marks"] = marks
    return slot


def pool(count: int, marks: float = 1, **criteria: Any) -> dict[str, Any]:
    return {"slot_type": "pool", "count": count, "marks": marks, "criteria": criteria}


@pytest.fixture
def make_test(client: AsyncClient, who: Identities) -> Callable[..., Any]:
    """Author a test with one section of the given slots, and publish it. Returns its public id."""

    async def _make(
        slots: list[dict[str, Any]],
        *,
        publish: bool = True,
        sections: list[dict[str, Any]] | None = None,
        **fields: Any,
    ) -> str:
        who.author()
        body: dict[str, Any] = {
            "title": "Module test",
            "kind": "practice",
            "duration_minutes": 30,
            "pass_mark_percent": 60,
            "sections": sections or [{"title": "Section 1", "slots": slots}],
            **fields,
        }
        created = await client.post("/api/v1/tests", json=body)
        assert created.status_code == 201, created.text
        test_id = created.json()["test"]["test_id"]
        if publish:
            submitted = await client.post(f"/api/v1/tests/{test_id}/submit")
            assert submitted.status_code == 200, submitted.text
            who.reviewer()
            approved = await client.post(f"/api/v1/tests/{test_id}/approve", json={})
            assert approved.status_code == 200, approved.text
        return str(test_id)

    return _make


# ----------------------------------------------------------------------------- code-execution stand-in


class FakeCodeExecution:
    """A stand-in for code-execution-service's internal API, served through httpx's mock transport."""

    def __init__(self) -> None:
        self.submissions: dict[str, dict[str, Any]] = {}
        self.calls: list[dict[str, Any]] = []
        self.fail_with: int | None = None  # answer every submit with this status
        self.next_id = 1755000000009000

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-Internal-Service-Token") == INTERNAL_TOKEN
        if request.method == "POST":
            body = json.loads(request.content)
            self.calls.append(body)
            if self.fail_with is not None:
                return httpx.Response(self.fail_with, json={"status": "error", "message": "nope"})
            key = request.headers["Idempotency-Key"]
            existing = self.submissions.get(key)
            if existing is None:
                self.next_id += 1
                existing = {"submission_id": str(self.next_id), "status": "queued", "reference": body["reference"], "score": 0, "verdict": None}
                self.submissions[key] = existing
            return httpx.Response(202, json={"submission": existing})
        submission_id = request.url.path.rsplit("/", 1)[-1]
        found = next((s for s in self.submissions.values() if s["submission_id"] == submission_id), None)
        if found is None:
            return httpx.Response(404, json={"message": "not found"})
        return httpx.Response(200, json={"submission": found})

    def finish(self, reference: str, *, score: int, verdict: str = "accepted", flagged: bool = False) -> dict[str, Any]:
        """Judge a queued submission; returns the ``submission.judged`` event payload code-execution would emit."""
        submission = next(s for s in self.submissions.values() if s["reference"] == reference)
        submission.update(status="completed", score=score, verdict=verdict, passed_count=score // 50, total_count=2, flagged=flagged, similarity_percent=90 if flagged else None)
        return {
            "submission_id": submission["submission_id"],
            "reference": reference,
            "verdict": verdict,
            "passed": score // 50,
            "total": 2,
            "score": score,
            "flagged": flagged,
            "similarity_percent": submission["similarity_percent"],
        }


@pytest.fixture
def code_exec() -> FakeCodeExecution:
    return FakeCodeExecution()


@pytest.fixture
def code_client(settings: Settings, code_exec: FakeCodeExecution) -> CodeExecutionClient:
    return CodeExecutionClient(settings, transport=httpx.MockTransport(code_exec.handler))


# ----------------------------------------------------------------------------- the worker, one step at a time


class Work:
    """Runs the worker's loops once, deterministically, instead of on a timer."""

    def __init__(self, sessionmaker, redis, settings, code_client) -> None:
        self.sessionmaker, self.redis, self.settings, self.code_client = sessionmaker, redis, settings, code_client

    async def flush(self) -> int:
        from app.worker.runner import flush_answers

        return await flush_answers(self.sessionmaker, self.redis, self.settings)

    async def sweep(self) -> int:
        from app.worker.runner import sweep_attempts

        return await sweep_attempts(self.sessionmaker, self.redis, self.settings)

    async def grade(self) -> int:
        from app.worker.runner import grade_submitted

        return await grade_submitted(self.sessionmaker, self.redis, self.settings)

    async def dispatch(self) -> int:
        from app.services.coding_service import dispatch_due

        return await dispatch_due(self.sessionmaker, self.code_client, self.settings, self.redis)

    async def reconcile(self) -> int:
        from app.services.coding_service import reconcile_due

        return await reconcile_due(self.sessionmaker, self.code_client, self.settings, self.redis)

    async def release(self) -> int:
        from app.worker.runner import release_results

        return await release_results(self.sessionmaker, self.redis, self.settings)

    async def everything(self) -> None:
        """What the worker does between two requests: time out, flush, grade, send code out."""
        await self.sweep()
        await self.flush()
        await self.grade()
        await self.dispatch()
        await self.release()


@pytest.fixture
def work(sessionmaker, redis, settings, code_client) -> Work:
    return Work(sessionmaker, redis, settings, code_client)


@pytest.fixture
def expire(sessionmaker, redis) -> Callable[..., Any]:
    """Make an attempt's deadline pass (the server clock is the authority, so the test moves the deadline)."""

    async def _expire(attempt_id: str, *, seconds_ago: int = 3600) -> None:
        from datetime import timedelta

        from sqlalchemy import update

        from app.core.time import utcnow
        from app.models.attempt import Attempt

        async with sessionmaker() as db:
            await db.execute(update(Attempt).where(Attempt.public_id == int(attempt_id)).values(deadline_at=utcnow() - timedelta(seconds=seconds_ago)))
            await db.commit()
        await redis.delete(f"assessment:attempt:{attempt_id}:meta")

    return _expire
