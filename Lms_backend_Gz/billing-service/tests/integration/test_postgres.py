"""What only a real PostgreSQL can prove: the migration (up, down, up again, checked for drift), and behaviour under real concurrency — ten invoices
issued at once get ten distinct gap-free numbers, one gateway webhook delivered five times pays once, and payments racing for the same balance never
overpay."""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import fakeredis.aioredis
import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.deps import _authenticate, get_payment_gateway
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.gateways.payment import PaymentGateway
from app.main import create_app
from app.models import Base
from app.models.billing import Invoice, Payment
from tests.conftest import (
    API,
    INSTITUTION,
    PROFILE,
    _settings,
    activate_subscription,
    add_price,
    make_claims,
    seed_orgs,
    set_profile,
    signed,
)

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def pg_url(tmp_path_factory) -> Iterator[str]:
    pgserver = pytest.importorskip("pgserver")
    server = pgserver.get_server(tmp_path_factory.mktemp("pg_service"), cleanup_mode="delete")
    server.psql("CREATE DATABASE lms_billing;")
    yield server.get_uri().rsplit("/", 1)[0].replace("postgresql://", "postgresql+asyncpg://", 1) + "/lms_billing"
    server.cleanup()


def alembic(pg_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env={**os.environ, "DATABASE_URL": pg_url}, capture_output=True, text=True, check=False)  # noqa: S603


@pytest.fixture(scope="module")
def migrated(pg_url: str) -> str:
    for step in (("upgrade", "head"), ("downgrade", "base"), ("upgrade", "head")):
        result = alembic(pg_url, *step)
        assert result.returncode == 0, f"alembic {' '.join(step)} failed:\n{result.stderr[-1500:]}"
    check = alembic(pg_url, "check")
    assert check.returncode == 0, f"the models and the migration disagree:\n{check.stdout[-800:]}{check.stderr[-800:]}"
    return pg_url


@pytest.fixture
def settings(migrated: str) -> Settings:
    return _settings(DATABASE_URL=migrated)


@pytest.fixture
async def db_engine(settings: Settings) -> AsyncIterator[AsyncEngine]:
    engine = build_engine(settings)
    async with engine.begin() as conn:
        tables = ", ".join(f'"{name}"' for name in Base.metadata.tables)
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))  # noqa: S608
    yield engine
    await engine.dispose()


@pytest.fixture
async def app(db_engine, settings, provider):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    fastapi_app = create_app(settings)
    fastapi_app.state.engine, fastapi_app.state.sessionmaker, fastapi_app.state.redis = db_engine, build_sessionmaker(db_engine), redis
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    fastapi_app.dependency_overrides[get_payment_gateway] = lambda: PaymentGateway(settings, transport=httpx.MockTransport(provider.handler))
    yield fastapi_app
    await redis.aclose()


@pytest.fixture
def sessionmaker(db_engine):
    return build_sessionmaker(db_engine)


def as_billing(app) -> AsyncClient:
    """A client with its own identity, independent of the shared one (needed to race several requests)."""
    claims = make_claims(user_id=1755000000210111, role="admin", organization_id=None, scopes=("billing.manage",))
    app.dependency_overrides[_authenticate] = lambda: claims
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _issued_invoices(client, who, send_event, count: int) -> list[dict]:
    await seed_orgs(send_event)
    await add_price(client, who)
    await set_profile(client, who, INSTITUTION, PROFILE)
    for n in range(count):
        await activate_subscription(send_event, subscription=str(1755000000214000 + n))
    who.billing()
    return (await client.get(f"{API}/invoices", params={"status": "draft", "per_page": 100})).json()["invoices"]


async def test_ten_invoices_issued_at_once_get_ten_distinct_gap_free_numbers(client, who, send_event, app):
    drafts = await _issued_invoices(client, who, send_event, 10)
    async with as_billing(app) as a:
        responses = await asyncio.gather(*(a.post(f"{API}/admin/invoices/{d['invoice_id']}/issue") for d in drafts))
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses if r.status_code != 200]
    numbers = sorted(int(r.json()["invoice"]["number"].rsplit("/", 1)[1]) for r in responses)
    assert numbers == list(range(1, 11))  # no duplicates, no gaps


async def test_one_webhook_delivered_five_times_at_once_pays_once(client, who, send_event, app, sessionmaker):
    drafts = await _issued_invoices(client, who, send_event, 1)
    who.billing()
    invoice_id = (await client.post(f"{API}/admin/invoices/{drafts[0]['invoice_id']}/issue")).json()["invoice"]["invoice_id"]
    who.head()
    order = (await client.post(f"{API}/invoices/{invoice_id}/payments/gateway", json={})).json()["gateway_payment"]
    raw, headers = signed({"event_id": "evt_race", "type": "payment.captured", "order_id": order["order_id"], "payment_id": "pay_race", "amount": order["amount"]})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as hook:
        responses = await asyncio.gather(*(hook.post(f"{API}/webhooks/payment", content=raw, headers=headers) for _ in range(5)))
    assert sorted(r.json()["result"] for r in responses).count("paid") == 1

    async with sessionmaker() as db:
        invoice = (await db.execute(select(Invoice))).scalar_one()
        succeeded = int((await db.execute(select(func.count()).select_from(Payment).where(Payment.status == "succeeded"))).scalar_one())
    assert invoice.amount_paid == order["amount"] and invoice.status == "paid" and succeeded == 1


async def test_payments_racing_for_the_same_balance_never_overpay(client, who, send_event, app, sessionmaker):
    drafts = await _issued_invoices(client, who, send_event, 1)
    who.billing()
    invoice = (await client.post(f"{API}/admin/invoices/{drafts[0]['invoice_id']}/issue")).json()["invoice"]
    half = invoice["total"] // 2 + 1  # two of these together exceed the total
    async with as_billing(app) as a, as_billing(app) as b:
        responses = await asyncio.gather(
            *(c.post(f"{API}/admin/invoices/{invoice['invoice_id']}/payments/manual", json={"amount": half, "reference": f"UTR {n}"}) for n, c in enumerate((a, b)))
        )
    assert sorted(r.status_code for r in responses) == [201, 409]
    async with sessionmaker() as db:
        assert (await db.execute(select(Invoice))).scalar_one().amount_paid == half
