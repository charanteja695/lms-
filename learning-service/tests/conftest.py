from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

import fakeredis.aioredis
import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response
from lms_common.auth import AccessTokenClaims
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.deps import _authenticate
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.main import create_app
from app.models import Base

TEST_USER_ID = 1755000000005001
TEST_SESSION_ID = 1755000000005002
TEST_ORG_ID = 1755000000005003
TEST_COURSE_ID = 1755000000005004
TEST_VERSION_ID = 1755000000005005
TEST_SUBSCRIPTION_ID = 1755000000005006
TEST_INTERNAL_TOKEN = "test-internal-service-token"


def _settings() -> Settings:
    return Settings(
        ENVIRONMENT="test",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        REDIS_URL="redis://localhost:6379/15",
        DOCS_ENABLED=False,
        RATE_LIMIT_ENABLED=False,
        LOG_JSON=False,
        INTERNAL_SERVICE_TOKEN=TEST_INTERNAL_TOKEN,
        SUBSCRIPTION_SERVICE_URL="http://subscription-service.test",
    )


# What user-management puts in a token by default (its permission catalog), for the permissions this service checks.
# What user-management's token carries by default: the permission-matrix cells plus the feature keys they imply.
ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "student": ("my_learning.view", "learning.study"),
    "staff": ("batches.view", "learning.batches.view"),
    "institution_head": (
        "batches.view", "batches.create", "batches.update", "batches.delete", "batches.revoke", "learning.batches.view", "learning.batches.manage",
    ),
}


def make_claims(
    *, user_id: int = TEST_USER_ID, scopes: tuple[str, ...] = (), role: str = "admin", organization_id: int | None = None, defaults: bool = True) -> AccessTokenClaims:
    scopes = (*ROLE_PERMISSIONS.get(role, ()), *scopes) if defaults else scopes  # "defaults": the role's own
    now = datetime.now(UTC)
    return AccessTokenClaims(
        user_id=user_id,
        session_id=TEST_SESSION_ID,
        role=role,
        organization_id=organization_id,
        organization_type="institution" if organization_id else None,
        scopes=scopes,
        token_version=0,
        token_id="test-token",
        issued_at=int(now.timestamp()),
        expires_at=now,
        # an admin looks after the test institution (accounts.manage reaches only the institutions an admin looks after)
        admin_organization_ids=(TEST_ORG_ID,) if role == "admin" else (),
    )


@pytest.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = build_engine(_settings())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def app(db_engine: AsyncEngine):
    settings = _settings()
    fastapi_app = create_app(settings)
    fastapi_app.state.engine = db_engine
    fastapi_app.state.sessionmaker = build_sessionmaker(db_engine)
    fastapi_app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    yield fastapi_app
    await fastapi_app.state.redis.aclose()


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def authed(app) -> Callable[..., AccessTokenClaims]:
    def _set(
        *, scopes: tuple[str, ...] = (), user_id: int = TEST_USER_ID, role: str = "admin", organization_id: int | None = None, defaults: bool = True
    ) -> AccessTokenClaims:
        claims = make_claims(user_id=user_id, scopes=scopes, role=role, organization_id=organization_id, defaults=defaults)
        app.dependency_overrides[_authenticate] = lambda: claims
        return claims

    yield _set
    app.dependency_overrides.pop(_authenticate, None)


@pytest.fixture
def as_institution_head(authed) -> Callable[..., AccessTokenClaims]:
    def _set(*, organization_id: int = TEST_ORG_ID, user_id: int = TEST_USER_ID) -> AccessTokenClaims:
        return authed(role="institution_head", organization_id=organization_id, user_id=user_id)

    return _set


@pytest.fixture
def as_admin(authed) -> Callable[..., AccessTokenClaims]:
    def _set(*, user_id: int = TEST_USER_ID) -> AccessTokenClaims:
        return authed(role="admin", scopes=("accounts.manage",), user_id=user_id)

    return _set


@pytest.fixture
def as_student(authed) -> Callable[..., AccessTokenClaims]:
    def _set(*, user_id: int, organization_id: int = TEST_ORG_ID) -> AccessTokenClaims:
        return authed(role="student", organization_id=organization_id, user_id=user_id)

    return _set


@pytest.fixture
async def seed_institution(app):
    async def _seed(organization_id: int = TEST_ORG_ID) -> None:
        from app.services.institution_ref_service import InstitutionRefService

        async with app.state.sessionmaker() as db:
            await InstitutionRefService(db).upsert(
                {"organization_id": str(organization_id), "name": "Springfield High", "code": "SPH-01", "status": "active"}
            )
            await db.commit()

    return _seed


def published_course_payload(*, course_id: int = TEST_COURSE_ID, version_id: int = TEST_VERSION_ID) -> dict:
    """Mirrors catalog-service's course.published payload (see ReviewService._published_structure_payload)."""
    return {
        "course_id": str(course_id),
        "version_id": str(version_id),
        "title": "A Course",
        "slug": "a-course",
        "unlock_mode": "sequential",
        "final_test_id": None,
        "final_pass_mark": 60,
        "final_test_attempts": 3,
        "final_test_cooldown_days": 7,
        "modules": [
            {
                "module_id": 1755000000005101,
                "title": "Module One",
                "position": 1,
                "pass_mark": 60,
                "module_test_id": None,
                "topics": [
                    {
                        "topic_id": 1755000000005201,
                        "title": "Topic One",
                        "position": 1,
                        "pass_mark": 60,
                        "topic_test_id": None,
                        "items": [
                            {"topic_item_id": 1755000000005301, "title": "Intro video", "position": 1, "item_type": "video", "required": True},
                            {"topic_item_id": 1755000000005302, "title": "Notes", "position": 2, "item_type": "notes", "required": True},
                        ],
                    }
                ],
            }
        ],
    }


@pytest.fixture
async def seed_course(app):
    async def _seed(**overrides) -> dict:
        from app.services.course_structure_service import CourseStructureService

        payload = published_course_payload(**overrides)
        async with app.state.sessionmaker() as db:
            await CourseStructureService(db).upsert_published(payload)
            await db.commit()
        return payload

    return _seed


@pytest.fixture
async def seed_entitlement(app):
    async def _seed(
        *, organization_id: int = TEST_ORG_ID, course_id: int = TEST_COURSE_ID, subscription_id: int = TEST_SUBSCRIPTION_ID
    ) -> None:
        await app.state.redis.hset(
            f"lms:entitlement:{organization_id}:{course_id}",
            mapping={"subscription_id": str(subscription_id), "seats_total": 10, "seats_used": 0, "expires_at": "2099-01-01T00:00:00"},
        )

    return _seed


@pytest.fixture
def mock_seats():
    """Mocks subscription-service's seat reserve/release endpoints (see app/clients/subscription_client.py).
    Always succeeds; tests that need a rejection override the route explicitly."""
    with respx.mock(base_url="http://subscription-service.test", assert_all_called=False) as router:
        router.post(url__regex=r"/api/v1/subscriptions/\d+/seats/reserve").mock(
            return_value=Response(200, json={"status": "success", "code": "SUCCESS", "message": "Seat reserved.", "seats": {"seats_total": 10, "seats_used": 1, "seats_available": 9}})
        )
        router.post(url__regex=r"/api/v1/subscriptions/\d+/seats/release").mock(
            return_value=Response(200, json={"status": "success", "code": "SUCCESS", "message": "Seat released.", "seats": {"seats_total": 10, "seats_used": 0, "seats_available": 10}})
        )
        yield router
