"""The learner store: a self-registered learner buys a course with Razorpay; a paid invoice announces `course.purchased` once."""

import json
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.gateways.payment import sign
from app.models.outbox_event import OutboxEvent
from tests.conftest import API, COURSE_PY, WEBHOOK_SECRET, _settings, add_price

LEARNERS_ORG, LEARNER, OTHER_LEARNER = 1755000000219001, 1755000000219101, 1755000000219102
KEY_SECRET = "rzp-test-key-secret"


class FakeRazorpay:
    """Razorpay's Orders API: basic auth, the order at the top level."""

    def __init__(self) -> None:
        self.orders: list[dict[str, Any]] = []
        self.auth: list[str | None] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.orders.append(body)
        self.auth.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"id": f"order_rzp{len(self.orders)}", "amount": body["amount"], "currency": body["currency"], "status": "created"})


@pytest.fixture
def settings():
    return _settings(PAYMENT_PROVIDER="razorpay", RAZORPAY_KEY_ID="rzp_test_key", RAZORPAY_KEY_SECRET=KEY_SECRET, RAZORPAY_API_URL="http://rzp.test/v1", LEARNER_ACCESS_DAYS=180)


@pytest.fixture
def provider() -> FakeRazorpay:
    return FakeRazorpay()


def learner(act_as, user_id: int = LEARNER):
    return act_as(user_id, role="student", organization_id=LEARNERS_ORG, scopes=("store.buy", "learning.study"), defaults=False)


def checkout_signature(order_id: str, payment_id: str) -> str:
    return sign(f"{order_id}|{payment_id}".encode(), KEY_SECRET)


async def _purchased_events(sessionmaker) -> list[dict[str, Any]]:
    async with sessionmaker() as db:
        return [e.payload for e in (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == "course.purchased"))).scalars()]


async def test_a_learner_sees_the_price_with_gst_buys_pays_and_the_course_is_announced_once(client, who, act_as, provider, sessionmaker):
    await add_price(client, who, unit_amount=499_900)  # ₹4,999
    learner(act_as)
    offers = (await client.get(f"{API}/store/offers")).json()
    assert offers["payments_available"] is True
    offer = offers["offers"][0]
    assert offer["course_id"] == str(COURSE_PY) and offer["gst"] == 89_982 and offer["total"] == 589_882 and offer["valid_days"] == 180

    bought = await client.post(f"{API}/store/courses/{COURSE_PY}/buy", json={"name": "Kiran Rao", "email": "kiran@example.com"})
    assert bought.status_code == 201, bought.text
    body = bought.json()
    assert body["checkout"] == {"provider": "razorpay", "key_id": "rzp_test_key", "order_id": "order_rzp1", "amount": 589_882, "currency": "INR", "seller_name": "LMS"}
    assert provider.orders[0]["amount"] == 589_882 and provider.auth[0].startswith("Basic ")
    assert body["purchase"]["status"] == "pending" and body["purchase"]["invoice_number"].startswith("INV/")

    purchase_id = body["purchase"]["purchase_id"]
    forged = await client.post(f"{API}/store/purchases/{purchase_id}/confirm", json={"razorpay_order_id": "order_rzp1", "razorpay_payment_id": "pay_1", "razorpay_signature": "0" * 64})
    assert forged.status_code == 400 and await _purchased_events(sessionmaker) == []

    paid = await client.post(
        f"{API}/store/purchases/{purchase_id}/confirm",
        json={"razorpay_order_id": "order_rzp1", "razorpay_payment_id": "pay_1", "razorpay_signature": checkout_signature("order_rzp1", "pay_1")},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["purchase"]["status"] == "paid"
    events = await _purchased_events(sessionmaker)
    assert len(events) == 1 and events[0]["user_id"] == str(LEARNER) and events[0]["course_id"] == str(COURSE_PY) and events[0]["valid_days"] == 180

    # Razorpay's webhook for the same payment arrives later: nothing happens twice
    raw = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_1", "order_id": "order_rzp1", "amount": 589_882}}}}).encode()
    hook = await client.post(f"{API}/webhooks/payment", content=raw, headers={"X-Razorpay-Signature": sign(raw, WEBHOOK_SECRET), "X-Razorpay-Event-Id": "evt_1", "Content-Type": "application/json"})
    assert hook.status_code == 200 and hook.json()["result"] == "ignored"
    assert len(await _purchased_events(sessionmaker)) == 1

    mine = (await client.get(f"{API}/store/purchases")).json()["purchases"]
    assert [p["status"] for p in mine] == ["paid"]
    learner(act_as, OTHER_LEARNER)
    assert (await client.get(f"{API}/store/purchases")).json()["purchases"] == []  # each sees their own only


async def test_the_webhook_alone_settles_a_purchase_when_the_browser_never_comes_back(client, who, act_as, sessionmaker):
    await add_price(client, who)
    learner(act_as)
    body = (await client.post(f"{API}/store/courses/{COURSE_PY}/buy", json={"name": "Kiran Rao"})).json()
    amount = body["checkout"]["amount"]
    raw = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_9", "order_id": body["checkout"]["order_id"], "amount": amount}}}}).encode()
    bad = await client.post(f"{API}/webhooks/payment", content=raw, headers={"X-Razorpay-Signature": "0" * 64, "Content-Type": "application/json"})
    assert bad.status_code == 401
    good = await client.post(f"{API}/webhooks/payment", content=raw, headers={"X-Razorpay-Signature": sign(raw, WEBHOOK_SECRET), "X-Razorpay-Event-Id": "evt_9", "Content-Type": "application/json"})
    assert good.json()["result"] == "paid"
    assert len(await _purchased_events(sessionmaker)) == 1


async def test_a_waiting_purchase_is_reused_and_only_learners_may_buy(client, who, act_as, provider):
    await add_price(client, who)
    learner(act_as)
    first = (await client.post(f"{API}/store/courses/{COURSE_PY}/buy", json={"name": "Kiran Rao"})).json()
    again = (await client.post(f"{API}/store/courses/{COURSE_PY}/buy", json={"name": "Kiran Rao"})).json()
    assert first["purchase"]["purchase_id"] == again["purchase"]["purchase_id"]  # one invoice, a fresh order
    assert len(provider.orders) == 2

    assert (await client.post(f"{API}/store/courses/1755000000299999/buy", json={"name": "Kiran Rao"})).status_code == 404
    who.head()
    assert (await client.get(f"{API}/store/offers")).status_code == 403  # an institution's people don't buy for themselves
    who.super_admin()
    assert (await client.get(f"{API}/store/offers")).status_code == 403


async def test_one_provider_payment_never_settles_two_orders(client, who, act_as, sessionmaker):
    await add_price(client, who)
    await add_price(client, who, code="1755000000211002", name="SQL")
    learner(act_as)
    first = (await client.post(f"{API}/store/courses/{COURSE_PY}/buy", json={"name": "Kiran Rao"})).json()
    second = (await client.post(f"{API}/store/courses/1755000000211002/buy", json={"name": "Kiran Rao"})).json()
    for bought in (first, second):
        order = bought["checkout"]["order_id"]
        response = await client.post(
            f"{API}/store/purchases/{bought['purchase']['purchase_id']}/confirm",
            json={"razorpay_order_id": order, "razorpay_payment_id": "pay_same", "razorpay_signature": checkout_signature(order, "pay_same")},
        )
        assert response.status_code == 200, response.text
    statuses = [p["status"] for p in (await client.get(f"{API}/store/purchases")).json()["purchases"]]
    assert sorted(statuses) == ["paid", "pending"] and len(await _purchased_events(sessionmaker)) == 1


async def test_a_course_price_carries_its_own_learner_access_days(client, who, act_as):
    price = await add_price(client, who, valid_days=90)
    assert price["meta"] == {"valid_days": 90}
    learner(act_as)
    assert (await client.get(f"{API}/store/offers")).json()["offers"][0]["valid_days"] == 90
    who.billing()
    changed = await client.patch(f"{API}/admin/prices/{price['price_id']}", json={"valid_days": 30})
    assert changed.json()["price"]["meta"] == {"valid_days": 30}


async def test_buying_is_closed_while_razorpay_keys_are_missing(app, client, who, act_as):
    from app.api.deps import get_payment_gateway
    from app.gateways.payment import PaymentGateway

    await add_price(client, who)
    bare = _settings(PAYMENT_PROVIDER="razorpay")
    app.dependency_overrides[get_payment_gateway] = lambda: PaymentGateway(bare)
    learner(act_as)
    assert (await client.get(f"{API}/store/offers")).json()["payments_available"] is False
    response = await client.post(f"{API}/store/courses/{COURSE_PY}/buy", json={"name": "Kiran Rao"})
    assert response.status_code == 503 and response.json()["code"] == "PAYMENT_GATEWAY_NOT_CONFIGURED"
