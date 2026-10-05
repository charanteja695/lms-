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

from app.api.deps import _authenticate, get_payment_gateway
from app.core.config import Settings, get_settings
from app.core.time import utcnow
from app.db.session import build_engine, build_sessionmaker
from app.events.consumers.router import dispatch
from app.gateways.payment import PaymentGateway, sign
from app.main import create_app
from app.models import Base

INSTITUTION, INSTITUTION_2, EMPLOYER = 1755000000210001, 1755000000210002, 1755000000210011
HEAD, HEAD_2, STAFF, EMP_ADMIN, RECRUITER = 1755000000210101, 1755000000210102, 1755000000210103, 1755000000210104, 1755000000210105
BILLING, OTHER_ADMIN, SUPER = 1755000000210111, 1755000000210112, 1755000000210113
COURSE_PY, COURSE_SQL = 1755000000211001, 1755000000211002
WEBHOOK_SECRET = "test-webhook-secret"
API = "/api/v1"


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "ENVIRONMENT": "test", "DATABASE_URL": "sqlite+aiosqlite:///:memory:", "REDIS_URL": "redis://localhost:6379/15", "DOCS_ENABLED": False, "RATE_LIMIT_ENABLED": False, "LOG_JSON": False,
        "SELLER_STATE": "Karnataka", "GST_RATE_PERCENT": 18, "PAYMENT_GATEWAY_URL": "http://pay.test", "PAYMENT_WEBHOOK_SECRET": WEBHOOK_SECRET,
    }
    values.update(overrides)
    return Settings(**values)


def make_claims(*, user_id: int, role: str, organization_id: int | None, scopes: tuple[str, ...] = ()) -> AccessTokenClaims:
    now = datetime.now(UTC)
    return AccessTokenClaims(
        user_id=user_id, session_id=1755000000210900, role=role, organization_id=organization_id, organization_type=None, scopes=scopes, token_version=0, token_id="test-token",
        issued_at=int(now.timestamp()), expires_at=now,
    )


class FakePaymentProvider:
    """The payment provider's order API, at the contract app/gateways/payment.py documents."""

    def __init__(self) -> None:
        self.orders: list[dict[str, Any]] = []
        self.status = 201

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.orders.append(body)
        if self.status >= 400:
            return httpx.Response(self.status, json={"error": "nope"})
        return httpx.Response(201, json={"order": {"id": f"order_{len(self.orders)}", "amount": body["amount"], "currency": body["currency"], "status": "created"}})


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
def provider() -> FakePaymentProvider:
    return FakePaymentProvider()


@pytest.fixture
async def app(db_engine, sessionmaker, settings, redis, provider):
    fastapi_app = create_app(settings)
    fastapi_app.state.engine, fastapi_app.state.sessionmaker, fastapi_app.state.redis = db_engine, sessionmaker, redis
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    fastapi_app.dependency_overrides[get_payment_gateway] = lambda: PaymentGateway(settings, transport=httpx.MockTransport(provider.handler))
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

    def head(self, user_id: int = HEAD, organization_id: int = INSTITUTION):
        return self._act_as(user_id, role="institution_head", organization_id=organization_id)

    def staff(self):
        return self._act_as(STAFF, role="staff", organization_id=INSTITUTION)

    def employer_admin(self, organization_id: int = EMPLOYER):
        return self._act_as(EMP_ADMIN, role="employer_admin", organization_id=organization_id)

    def recruiter(self):
        return self._act_as(RECRUITER, role="recruiter", organization_id=EMPLOYER)

    def billing(self):
        return self._act_as(BILLING, role="admin", organization_id=None, scopes=("billing.manage",))

    def other_admin(self):
        return self._act_as(OTHER_ADMIN, role="admin", organization_id=None, scopes=("accounts.manage",))

    def super_admin(self):
        return self._act_as(SUPER, role="super_admin", organization_id=None)


@pytest.fixture
def who(act_as) -> Identities:
    return Identities(act_as)


@pytest.fixture
def send_event(sessionmaker, settings) -> Callable[..., Any]:
    async def _send(event_type: str, payload: dict[str, Any], *, event_id: str | None = None, occurred_time: datetime | None = None) -> None:
        event = Event(event_id=event_id or uuid.uuid4().hex, event_type=event_type, aggregate_type="x", occurred_time=occurred_time or utcnow(), payload=json.loads(json.dumps(payload)))
        async with sessionmaker() as db:
            await dispatch(db, event, settings)
            await db.commit()

    return _send


def signed(body: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(body).encode()
    return raw, {"X-Signature": sign(raw, WEBHOOK_SECRET), "Content-Type": "application/json"}


def org_payload(org_id: int, name: str, kind: str) -> dict[str, Any]:
    return {"organization_id": str(org_id), "name": name, "code": name[:4].upper(), "organization_type": kind, "status": "active", "admin_user_id": "1"}


async def seed_orgs(send_event) -> None:
    await send_event("institution.created", org_payload(INSTITUTION, "Anna University", "institution"))
    await send_event("institution.created", org_payload(INSTITUTION_2, "Bharat College", "institution"))
    await send_event("employer.created", org_payload(EMPLOYER, "Acme Labs", "employer"))


PROFILE = {"legal_name": "Anna University", "gstin": "29ABCDE1234F1Z5", "state": "Karnataka", "address": "1 College Road, Bengaluru", "email": "accounts@anna.example"}
PROFILE_OTHER_STATE = {**PROFILE, "state": "Tamil Nadu", "gstin": "33ABCDE1234F1Z5"}


async def set_profile(client, who, org: int = INSTITUTION, profile: dict[str, Any] | None = None) -> None:
    who.billing()
    response = await client.put(f"{API}/admin/organizations/{org}/billing-profile", json=profile or PROFILE)
    assert response.status_code == 200, response.text


async def add_price(client, who, *, kind: str = "course_seat", code: str = str(COURSE_PY), name: str = "Python Programming", unit_amount: int = 1_000_000, **extra: Any) -> dict[str, Any]:
    who.billing()
    response = await client.post(f"{API}/admin/prices", json={"kind": kind, "code": code, "name": name, "unit_amount": unit_amount, **extra})
    assert response.status_code == 201, response.text
    return response.json()["price"]


async def activate_subscription(send_event, *, org: int = INSTITUTION, course: int = COURSE_PY, seats: int = 100, days: int = 365, subscription: str | None = None) -> str:
    """subscription-service's real event; the invoice is drafted from it."""
    now = utcnow()
    from datetime import timedelta

    sub_id = subscription or str(uuid.uuid4().int % 10**16 + 10**15)
    await send_event(
        "subscription.activated",
        {"subscription_id": sub_id, "organization_id": str(org), "course_id": str(course), "seats_total": seats, "ends_at": (now + timedelta(days=days)).isoformat()},
        occurred_time=now,
    )
    return sub_id


async def first_draft(client, who, status: str = "draft") -> dict[str, Any]:
    who.billing()
    invoices = (await client.get(f"{API}/invoices", params={"status": status})).json()["invoices"]
    assert invoices, f"no {status} invoice"
    return invoices[0]
