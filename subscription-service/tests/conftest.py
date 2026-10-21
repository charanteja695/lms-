from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from lms_common.auth import AccessTokenClaims
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.deps import _authenticate
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.main import create_app
from app.models import Base

TEST_USER_ID = 1755000000004001
TEST_SESSION_ID = 1755000000004002
TEST_ORG_ID = 1755000000004003
TEST_INTERNAL_TOKEN = "test-internal-service-token"
INTERNAL_HEADERS = {"X-Internal-Service-Token": TEST_INTERNAL_TOKEN}


def _settings() -> Settings:
    return Settings(
        ENVIRONMENT="test",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        REDIS_URL="redis://localhost:6379/15",
        DOCS_ENABLED=False,
        RATE_LIMIT_ENABLED=False,
        INTERNAL_SERVICE_TOKEN=TEST_INTERNAL_TOKEN,
        LOG_JSON=False,
    )


# What user-management puts in a token by default (its permission catalog), for the permissions this service checks.
# What user-management's token carries by default: the permission-matrix cells plus the feature key they imply.
ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {"institution_head": ("course_requests.view", "course_requests.create", "subscriptions.request")}


def make_claims(
    *,
    user_id: int = TEST_USER_ID,
    scopes: tuple[str, ...] = (),
    role: str = "admin",
    organization_id: int | None = None, defaults: bool = True) -> AccessTokenClaims:
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


TEST_COURSE_ID = 1755000000004555


@pytest.fixture
async def seed_refs(app):
    """Seeds an active institution and a published course via the real event-consumer upsert
    logic (see app/services/institution_ref_service.py / course_ref_service.py), the way the
    worker would after consuming institution.created / course.published."""

    async def _seed(*, organization_id: int = TEST_ORG_ID, course_id: int = TEST_COURSE_ID) -> None:
        from app.domain.enums import CourseAvailability
        from app.services.course_ref_service import CourseRefService
        from app.services.institution_ref_service import InstitutionRefService

        async with app.state.sessionmaker() as db:
            await InstitutionRefService(db).upsert(
                {"organization_id": str(organization_id), "name": "Springfield High", "code": "SPH-01", "status": "active"}
            )
            await CourseRefService(db).upsert(
                {"course_id": str(course_id), "title": "A Course", "slug": "a-course"}, status=CourseAvailability.PUBLISHED
            )
            await db.commit()

    return _seed
