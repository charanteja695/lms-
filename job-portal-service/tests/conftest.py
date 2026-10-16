import json
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import fakeredis.aioredis
import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from lms_common.auth import AccessTokenClaims
from lms_common.events import Event
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.api.deps import _authenticate, get_career, get_gateway
from app.clients.assessment import AssessmentClient
from app.clients.career import CareerClient
from app.clients.gateway import GatewayClient
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.events.consumers.router import dispatch
from app.main import create_app
from app.models import Base
from app.worker.work import run_due

ORG_A, ORG_B = 1755000000070001, 1755000000070002  # institutions
EMP_A, EMP_B = 1755000000070011, 1755000000070012  # employers
STUDENT, STUDENT_2, STUDENT_3, STUDENT_4 = 1755000000070101, 1755000000070102, 1755000000070103, 1755000000070104
RECRUITER, EMP_ADMIN, RECRUITER_B, EMP_ADMIN_B = 1755000000070111, 1755000000070112, 1755000000070113, 1755000000070114
HEAD_A, STAFF_A, HEAD_B, MANAGER, SUPER = 1755000000070121, 1755000000070122, 1755000000070123, 1755000000070131, 1755000000070132
COURSE_PY, COURSE_SQL, COURSE_WEB = 1755000000071001, 1755000000071002, 1755000000071003
TEST_ID, PLAN_ID = 1755000000072001, 1755000000072002
RESUME = 1755000000073001
INTERNAL_TOKEN = "test-internal-service-token-0123456789"
API = "/api/v1"


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "ENVIRONMENT": "test", "DATABASE_URL": "sqlite+aiosqlite:///:memory:", "REDIS_URL": "redis://localhost:6379/15", "DOCS_ENABLED": False, "RATE_LIMIT_ENABLED": False,
        "LOG_JSON": False, "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN, "AI_GATEWAY_URL": "http://gateway.test", "ASSESSMENT_SERVICE_URL": "http://assessment.test",
        "CAREER_SERVICE_URL": "http://career.test", "WORKER_POLL_SECONDS": 0.02, "MATCH_BATCH_SIZE": 3,
    }
    values.update(overrides)
    return Settings(**values)


# What user-management puts in a token by default (its permission catalog), for the permissions this service checks.
ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {"student": ("jobs.apply",), "staff": ("jobs.placements",), "institution_head": ("jobs.placements", "jobs.drives.propose"), "employer_admin": ("jobs.hire", "jobs.company.manage"), "recruiter": ("jobs.hire",)}


def make_claims(*, user_id: int, role: str, organization_id: int | None, scopes: tuple[str, ...] = (), defaults: bool = True) -> AccessTokenClaims:
    scopes = (*ROLE_PERMISSIONS.get(role, ()), *scopes) if defaults else scopes  # "defaults": the role's own
    now = datetime.now(UTC)
    return AccessTokenClaims(
        user_id=user_id, session_id=1755000000070002, role=role, organization_id=organization_id, organization_type="institution" if role in {"student", "staff", "institution_head"} else "employer" if role in {"employer_admin", "recruiter"} else None,
        scopes=scopes, token_version=0, token_id="test-token", issued_at=int(now.timestamp()), expires_at=now,
    )


# ---------------------------------------------------------------- fakes of the services this one calls
class FakeGateway:
    """ai-gateway: completions (scripted) and embeddings (a bag-of-words vector, so similar texts are close)."""

    DIMS = 32

    def __init__(self) -> None:
        self.completions: list[dict[str, Any]] = []
        self.embeddings: list[list[str]] = []
        self.replies: list[str] = []
        self.completion_error: tuple[int, str] | None = None
        self.embedding_error: tuple[int, str] | None = None
        self.blocked = False

    def reply(self, text: str) -> None:
        self.replies.append(text)

    @staticmethod
    def vector(text: str) -> list[float]:
        import zlib

        from app.matching.text import tokens

        out = [0.0] * FakeGateway.DIMS
        for token in tokens(text):
            out[zlib.crc32(token.encode()) % FakeGateway.DIMS] += 1.0
        return out

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-Internal-Service-Token") == INTERNAL_TOKEN
        body = json.loads(request.content)
        if request.url.path.endswith("/embeddings"):
            self.embeddings.append(body["texts"])
            if self.embedding_error:
                return httpx.Response(self.embedding_error[0], json={"status": "error", "code": self.embedding_error[1]})
            data = {"call_id": "1755000000099002", "vectors": [self.vector(t) for t in body["texts"]], "model": "voyage-3", "provider": "voyage", "tokens": 1, "cost_cents": 0}
            return httpx.Response(200, json={"status": "success", "code": "SUCCESS", "message": "", "embedding": data})
        self.completions.append(body)
        if self.completion_error:
            return httpx.Response(self.completion_error[0], json={"status": "error", "code": self.completion_error[1]})
        status = "blocked" if self.blocked else "ok"
        text = "" if self.blocked else (self.replies.pop(0) if self.replies else json.dumps({"score": 80, "reasons": ["Relevant skills"], "red_flags": []}))
        completion = {"call_id": "1755000000099001", "status": status, "content": text, "model": "claude-sonnet-5", "provider": "anthropic", "guardrail_flags": [], "prompt_version": 3}
        return httpx.Response(200, json={"status": "success", "code": "SUCCESS", "message": "", "completion": completion})


class FakeCareer:
    """career-service's snapshot endpoint."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.owners: dict[int, int] = {RESUME: STUDENT}  # resume id -> its owner
        self.down = False
        self.version = 0

    def document(self, user_id: int) -> dict[str, Any]:
        return {
            "personal": {"name": "Asha Rao", "email": "asha@example.com", "phone": "+91 98765 43210", "location": "Chennai", "links": [{"label": "GitHub", "url": "https://github.com/asha"}]},
            "summary": "Backend developer.",
            "sections": [
                {"key": "experience", "title": "Experience", "entries": [{"heading": "Software Intern", "subheading": "Acme Labs", "dates": "May 2025 – Jul 2025", "bullets": ["Built a REST API in Python serving 2000 requests per minute, reachable at https://acme.example/api", "Mailed asha@example.com the report"], "verified": False, "kind": "experience", "item_id": "1"}]},
                {"key": "skills", "title": "Skills", "entries": [{"heading": "Python", "subheading": None, "dates": None, "bullets": [], "verified": False, "kind": "skill", "item_id": "2"}]},
            ],
        }

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-Internal-Service-Token") == INTERNAL_TOKEN
        body = json.loads(request.content)
        resume_id = int(request.url.path.split("/")[-2])
        self.calls.append({"resume_id": resume_id, **body})
        if self.down:
            return httpx.Response(503, json={"status": "error", "code": "DOWN"})
        if self.owners.get(resume_id) != int(body["user_id"]):
            return httpx.Response(404, json={"status": "error", "code": "RESUME_NOT_FOUND"})
        self.version += 1
        return httpx.Response(201, json={"status": "success", "resume_id": str(resume_id), "user_id": body["user_id"], "title": "Backend Developer", "target_role": None, "version_no": self.version, "template_key": "classic", "ats_score": 72, "document": self.document(int(body["user_id"]))})


class FakeAssessment:
    """assessment-service's invitation endpoint."""

    def __init__(self) -> None:
        self.invites: list[dict[str, Any]] = []
        self.status = 201
        self.code: str | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-Internal-Service-Token") == INTERNAL_TOKEN
        body = json.loads(request.content)
        self.invites.append(body)
        if self.status >= 400:
            return httpx.Response(self.status, json={"status": "error", "code": self.code or "ERROR"})
        return httpx.Response(201, json={"status": "success", "assignment": {"test_id": body["test_id"], "user_id": body["user_id"], "reference": body["reference"]}})


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
def career() -> FakeCareer:
    return FakeCareer()


@pytest.fixture
def assessment() -> FakeAssessment:
    return FakeAssessment()


@pytest.fixture
def clients(settings, gateway, career, assessment) -> tuple[GatewayClient, CareerClient, AssessmentClient]:
    return (
        GatewayClient(settings, transport=httpx.MockTransport(gateway.handler)),
        CareerClient(settings, transport=httpx.MockTransport(career.handler)),
        AssessmentClient(settings, transport=httpx.MockTransport(assessment.handler)),
    )


@pytest.fixture
async def app(db_engine, sessionmaker, settings, redis, clients):
    fastapi_app = create_app(settings)
    fastapi_app.state.engine, fastapi_app.state.sessionmaker, fastapi_app.state.redis = db_engine, sessionmaker, redis
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    fastapi_app.dependency_overrides[get_gateway] = lambda: clients[0]
    fastapi_app.dependency_overrides[get_career] = lambda: clients[1]
    yield fastapi_app


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def act_as(app) -> Callable[..., AccessTokenClaims]:
    def _set(user_id: int, *, role: str, organization_id: int | None, scopes: tuple[str, ...] = (), defaults: bool = True) -> AccessTokenClaims:
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

    def recruiter(self, user_id: int = RECRUITER, organization_id: int = EMP_A):
        return self._act_as(user_id, role="recruiter", organization_id=organization_id)

    def employer_admin(self, user_id: int = EMP_ADMIN, organization_id: int = EMP_A):
        return self._act_as(user_id, role="employer_admin", organization_id=organization_id)

    def manager(self):
        return self._act_as(MANAGER, role="admin", organization_id=None, scopes=("careers.manage",))

    def other_admin(self):
        return self._act_as(SUPER + 1, role="admin", organization_id=None, scopes=("support.manage",))

    def staff(self, user_id: int = STAFF_A, organization_id: int = ORG_A):
        return self._act_as(user_id, role="staff", organization_id=organization_id)

    def head(self, user_id: int = HEAD_A, organization_id: int = ORG_A):
        return self._act_as(user_id, role="institution_head", organization_id=organization_id)


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
    """Run the worker's queue until it is empty (each item may queue follow-ups), like the worker loop would."""

    async def _run(limit: int = 50) -> int:
        total = 0
        for _ in range(limit):
            done = await run_due(sessionmaker, settings, clients[0], clients[2])
            if not done:
                break
            total += done
        return total

    return _run


# ---------------------------------------------------------------- the world
def org_payload(org_id: int, name: str, kind: str, *, status: str = "active", industry: str | None = None) -> dict[str, Any]:
    return {"organization_id": str(org_id), "name": name, "code": name[:4].upper(), "organization_type": kind, "industry": industry, "status": status, "admin_user_id": "1"}


def user_payload(user_id: int, first: str, last: str, role: str, org: int | None, *, email: str | None = None) -> dict[str, Any]:
    return {"user_id": str(user_id), "email": email or f"{first.lower()}@example.com", "first_name": first, "last_name": last, "role": role, "status": "active", "organization_id": str(org) if org else None}


def facts(*, skills=("Python", "SQL"), technologies=("FastAPI",), certificates=(COURSE_PY,), scores=((COURSE_PY, 91.5),), graduation_year=2026, months=6, location="Chennai, India",
          roles=("Backend Developer",), titles=("Software Intern",)) -> dict[str, Any]:
    return {
        "skills": list(skills), "technologies": list(technologies), "job_titles": list(titles), "experience_months": months, "projects": 1,
        "education": [{"degree": "B.Tech", "field": "Computer Science", "end_year": graduation_year}], "graduation_year": graduation_year,
        "certificates": [str(c) for c in certificates], "scores": [{"course_id": str(c), "best_percent": p} for c, p in scores], "location": location, "target_roles": list(roles), "headline": "Aspiring developer",
    }


_revisions: dict[int, int] = {}


async def profile_event(send_event, user_id: int, org: int | None = ORG_A, **kw: Any) -> None:
    _revisions[user_id] = _revisions.get(user_id, 0) + 1
    await send_event("skill_profile.updated", {"user_id": str(user_id), "organization_id": str(org) if org else None, "revision": _revisions[user_id], "facts": facts(**kw)})


async def seed_world(send_event) -> None:
    """Two institutions, two employers, their people, and three published courses."""
    await send_event("institution.created", org_payload(ORG_A, "Anna University", "institution"))
    await send_event("institution.created", org_payload(ORG_B, "Bharat College", "institution"))
    await send_event("employer.created", org_payload(EMP_A, "Acme Labs", "employer", industry="Software"))
    await send_event("employer.created", org_payload(EMP_B, "Beta Works", "employer", industry="Consulting"))
    for course, title in ((COURSE_PY, "Python Programming"), (COURSE_SQL, "SQL for Data"), (COURSE_WEB, "Web Design")):
        await send_event("course.published", {"course_id": str(course), "title": title})
    for user in (user_payload(STUDENT, "Asha", "Rao", "student", ORG_A), user_payload(STUDENT_2, "Ben", "Iyer", "student", ORG_B), user_payload(STUDENT_3, "Chitra", "Nair", "student", ORG_A),
                 user_payload(STUDENT_4, "Dev", "Shah", "student", ORG_A), user_payload(RECRUITER, "Rita", "Recruiter", "recruiter", EMP_A), user_payload(EMP_ADMIN, "Adam", "Admin", "employer_admin", EMP_A)):
        await send_event("user.created", user)


def job_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": "Backend Developer", "description": "Build and run REST APIs with Python and FastAPI on PostgreSQL. You will own services end to end with a small, friendly team.",
        "employment_type": "full_time", "location_type": "onsite", "locations": ["Chennai"], "experience_min_months": 0, "ctc_min": 600_000, "ctc_max": 1_200_000, "openings": 2,
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"], "preferred_skills": ["AWS"],
        "deadline_at": (datetime.now(UTC) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    body.update(overrides)
    return body


async def verify_employer(client, who, *, org: int = EMP_A) -> None:
    who.employer_admin(EMP_ADMIN if org == EMP_A else EMP_ADMIN_B, org)
    await client.patch(f"{API}/employer/profile", json={"about": "We build developer tools.", "website": "https://acme.example", "industry": "Software", "company_size": "51-200", "headquarters": "Chennai"})
    assert (await client.post(f"{API}/employer/profile/submit")).status_code == 200
    who.manager()
    assert (await client.post(f"{API}/admin/employers/{org}/review", json={"approve": True})).status_code == 200


async def open_job(client, who, work, *, org: int = EMP_A, **overrides: Any) -> str:
    """Draft, submit, approve a job and run the matching work; returns the job id."""
    who.recruiter(RECRUITER if org == EMP_A else RECRUITER_B, org)
    created = await client.post(f"{API}/employer/jobs", json=job_body(**overrides))
    assert created.status_code == 201, created.text
    job_id = created.json()["job"]["job_id"]
    assert (await client.post(f"{API}/employer/jobs/{job_id}/submit")).status_code == 200
    who.manager()
    assert (await client.post(f"{API}/admin/jobs/{job_id}/review", json={"approve": True})).status_code == 200
    await work()
    return job_id


async def hiring_world(client, who, send_event, work, *, students=(STUDENT,), **job: Any) -> str:
    """A verified employer with one open job, and verified candidates ready to apply; returns the job id."""
    await seed_world(send_event)
    for user in students:
        await profile_event(send_event, user, ORG_A if user != STUDENT_2 else ORG_B, skills=("Python", "SQL", "Docker"), technologies=("FastAPI", "PostgreSQL"), certificates=(COURSE_PY,), scores=((COURSE_PY, 90.0),))
    await verify_employer(client, who)
    return await open_job(client, who, work, **job)


async def apply(client, who, job_id: str, *, user: int = STUDENT, org: int = ORG_A, career: FakeCareer | None = None) -> dict[str, Any]:
    if career is not None:
        career.owners[RESUME] = user
    who.student(user, org)
    response = await client.post(f"{API}/job-board/{job_id}/apply", json={"resume_id": str(RESUME), "cover_note": "I would love to join."})
    assert response.status_code == 201, response.text
    return response.json()["application"]


FULL_PIPELINE = {"assessment": {"test_id": str(TEST_ID), "min_percent": 60}, "ai_interview": {"plan_id": str(PLAN_ID)}, "hr_interview": True}
