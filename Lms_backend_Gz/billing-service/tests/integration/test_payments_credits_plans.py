"""Payments (manual always; the gateway a contract only), credit notes, and employer plans (docs/PRODUCT.md §5.10)."""

from datetime import timedelta

from sqlalchemy import select

from app.core.time import utcnow
from app.models.billing import OrgPlan
from app.models.outbox_event import OutboxEvent
from app.services.plan_service import PlanService
from tests.conftest import (
    API,
    EMPLOYER,
    INSTITUTION,
    PROFILE,
    activate_subscription,
    add_price,
    first_draft,
    seed_orgs,
    set_profile,
    signed,
)


async def _issued(client, who, send_event, *, seats: int = 100) -> dict:
    await seed_orgs(send_event)
    await add_price(client, who)
    await set_profile(client, who, INSTITUTION, PROFILE)
    await activate_subscription(send_event, seats=seats)
    draft = await first_draft(client, who)
    who.billing()
    return (await client.post(f"{API}/admin/invoices/{draft['invoice_id']}/issue")).json()["invoice"]


async def _events(sessionmaker, event_type: str) -> list[OutboxEvent]:
    async with sessionmaker() as db:
        return list((await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == event_type))).scalars())


# ---------------------------------------------------------------- manual payments
async def test_manual_payments_add_up_and_the_invoice_is_paid_when_they_cover_it(client, who, send_event, sessionmaker):
    invoice = await _issued(client, who, send_event)
    who.billing()
    first = await client.post(f"{API}/admin/invoices/{invoice['invoice_id']}/payments/manual", json={"amount": 100_000_000, "reference": "UTR 123456", "method": "bank transfer"})
    assert first.status_code == 201, first.text
    partly = (await client.get(f"{API}/invoices/{invoice['invoice_id']}")).json()["invoice"]
    assert partly["status"] == "issued" and partly["amount_paid"] == 100_000_000 and partly["balance_due"] == 18_000_000

    second = await client.post(f"{API}/admin/invoices/{invoice['invoice_id']}/payments/manual", json={"amount": 18_000_000, "reference": "UTR 999"})
    assert second.status_code == 201
    paid = (await client.get(f"{API}/invoices/{invoice['invoice_id']}")).json()["invoice"]
    assert paid["status"] == "paid" and paid["balance_due"] == 0 and len(paid["payments"]) == 2
    assert len(await _events(sessionmaker, "invoice.paid")) == 1

    after = await client.post(f"{API}/admin/invoices/{invoice['invoice_id']}/payments/manual", json={"amount": 1, "reference": "late"})
    assert after.status_code == 409 and after.json()["code"] == "INVOICE_NOT_PAYABLE"


async def test_a_payment_cannot_exceed_what_is_owed_or_be_zero(client, who, send_event):
    invoice = await _issued(client, who, send_event)
    who.billing()
    over = await client.post(f"{API}/admin/invoices/{invoice['invoice_id']}/payments/manual", json={"amount": 118_000_001, "reference": "too much"})
    assert over.status_code == 409 and over.json()["code"] == "AMOUNT_EXCEEDS_BALANCE"
    assert (await client.post(f"{API}/admin/invoices/{invoice['invoice_id']}/payments/manual", json={"amount": 0, "reference": "zero"})).status_code == 422


async def test_a_paid_invoice_cannot_be_voided(client, who, send_event):
    invoice = await _issued(client, who, send_event)
    who.billing()
    await client.post(f"{API}/admin/invoices/{invoice['invoice_id']}/payments/manual", json={"amount": 1000, "reference": "part"})
    refused = await client.post(f"{API}/admin/invoices/{invoice['invoice_id']}/void", json={"reason": "changed my mind"})
    assert refused.status_code == 409 and refused.json()["code"] == "INVOICE_NOT_VOIDABLE"


# ---------------------------------------------------------------- the gateway
async def test_an_organisation_starts_an_online_payment_and_the_signed_webhook_settles_it(client, who, send_event, provider, sessionmaker):
    invoice = await _issued(client, who, send_event)
    who.head()
    started = await client.post(f"{API}/invoices/{invoice['invoice_id']}/payments/gateway", json={})
    assert started.status_code == 201, started.text
    order = started.json()["gateway_payment"]
    assert order["amount"] == 118_000_000 and provider.orders[0]["receipt"] == invoice["number"]

    raw, headers = signed({"event_id": "evt_1", "type": "payment.captured", "order_id": order["order_id"], "payment_id": "pay_1", "amount": 118_000_000})
    done = await client.post(f"{API}/webhooks/payment", content=raw, headers=headers)
    assert done.status_code == 200 and done.json()["result"] == "paid"
    assert (await client.get(f"{API}/invoices/{invoice['invoice_id']}")).json()["invoice"]["status"] == "paid"

    replay = await client.post(f"{API}/webhooks/payment", content=raw, headers=headers)
    assert replay.status_code == 200 and replay.json()["result"] == "duplicate"
    assert len(await _events(sessionmaker, "invoice.paid")) == 1


async def test_a_webhook_with_a_bad_signature_is_refused_and_changes_nothing(client, who, send_event):
    invoice = await _issued(client, who, send_event)
    who.head()
    order = (await client.post(f"{API}/invoices/{invoice['invoice_id']}/payments/gateway", json={})).json()["gateway_payment"]
    raw, _ = signed({"event_id": "evt_2", "type": "payment.captured", "order_id": order["order_id"], "payment_id": "pay_2", "amount": 118_000_000})
    forged = await client.post(f"{API}/webhooks/payment", content=raw, headers={"X-Signature": "0" * 64, "Content-Type": "application/json"})
    assert forged.status_code == 401
    assert (await client.post(f"{API}/webhooks/payment", content=raw)).status_code == 401
    assert (await client.get(f"{API}/invoices/{invoice['invoice_id']}")).json()["invoice"]["status"] == "issued"


async def test_a_failed_or_mismatched_payment_does_not_settle_the_invoice(client, who, send_event):
    invoice = await _issued(client, who, send_event)
    who.head()
    first = (await client.post(f"{API}/invoices/{invoice['invoice_id']}/payments/gateway", json={"amount": 1000})).json()["gateway_payment"]
    wrong, headers = signed({"event_id": "evt_3", "type": "payment.captured", "order_id": first["order_id"], "payment_id": "p", "amount": 999})
    assert (await client.post(f"{API}/webhooks/payment", content=wrong, headers=headers)).json()["result"] == "rejected"
    second = (await client.post(f"{API}/invoices/{invoice['invoice_id']}/payments/gateway", json={"amount": 1000})).json()["gateway_payment"]
    failed, headers = signed({"event_id": "evt_4", "type": "payment.failed", "order_id": second["order_id"]})
    assert (await client.post(f"{API}/webhooks/payment", content=failed, headers=headers)).json()["result"] == "failed"
    assert (await client.get(f"{API}/invoices/{invoice['invoice_id']}")).json()["invoice"]["amount_paid"] == 0


async def test_an_unknown_order_is_acknowledged_so_the_provider_stops_retrying(client):
    raw, headers = signed({"event_id": "evt_5", "type": "payment.captured", "order_id": "order_missing", "payment_id": "p", "amount": 1})
    response = await client.post(f"{API}/webhooks/payment", content=raw, headers=headers)
    assert response.status_code == 200 and response.json()["result"] == "ignored"


async def test_online_payment_answers_503_when_no_gateway_is_configured_but_manual_still_works(app, client, who, send_event, settings):
    from app.api.deps import get_payment_gateway
    from app.gateways.payment import PaymentGateway
    from tests.conftest import _settings

    invoice = await _issued(client, who, send_event)
    bare = _settings(PAYMENT_GATEWAY_URL="")
    app.dependency_overrides[get_payment_gateway] = lambda: PaymentGateway(bare)
    who.head()
    unavailable = await client.post(f"{API}/invoices/{invoice['invoice_id']}/payments/gateway", json={})
    assert unavailable.status_code == 503 and unavailable.json()["code"] == "PAYMENT_GATEWAY_NOT_CONFIGURED"
    who.billing()
    assert (await client.post(f"{API}/admin/invoices/{invoice['invoice_id']}/payments/manual", json={"amount": 118_000_000, "reference": "cheque 42"})).status_code == 201


async def test_a_provider_outage_is_a_503_and_leaves_no_payment_behind(client, who, send_event, provider):
    invoice = await _issued(client, who, send_event)
    provider.status = 500
    who.head()
    response = await client.post(f"{API}/invoices/{invoice['invoice_id']}/payments/gateway", json={})
    assert response.status_code == 503 and response.json()["code"] == "PAYMENT_GATEWAY_UNAVAILABLE"
    assert (await client.get(f"{API}/invoices/{invoice['invoice_id']}")).json()["invoice"]["payments"] == []


# ---------------------------------------------------------------- credit notes
async def test_a_credit_note_reduces_what_is_owed_with_its_own_gap_free_number(client, who, send_event):
    invoice = await _issued(client, who, send_event)
    who.billing()
    note = await client.post(f"{API}/admin/invoices/{invoice['invoice_id']}/credit-notes", json={"taxable_amount": 10_000_000, "reason": "Fewer seats than billed"})
    assert note.status_code == 201, note.text
    body = note.json()["credit_note"]
    assert body["number"].startswith("CN/") and body["number"].endswith("/000001") and (body["cgst"], body["sgst"]) == (900_000, 900_000) and body["total"] == 11_800_000
    after = (await client.get(f"{API}/invoices/{invoice['invoice_id']}")).json()["invoice"]
    assert after["balance_due"] == 118_000_000 - 11_800_000 and after["total"] == 118_000_000  # the original is untouched


async def test_crediting_the_whole_invoice_leaves_no_rounding_remainder_and_settles_it(client, who, send_event):
    invoice = await _issued(client, who, send_event)
    who.billing()
    await client.post(f"{API}/admin/invoices/{invoice['invoice_id']}/credit-notes", json={"taxable_amount": 33_333_333, "reason": "First part"})
    last = await client.post(f"{API}/admin/invoices/{invoice['invoice_id']}/credit-notes", json={"taxable_amount": 100_000_000 - 33_333_333, "reason": "The rest"})
    assert last.status_code == 201
    detail = (await client.get(f"{API}/invoices/{invoice['invoice_id']}")).json()["invoice"]
    assert sum(n["total"] for n in detail["credit_notes"]) == detail["total"] and detail["balance_due"] == 0 and detail["status"] == "paid"
    assert (await client.post(f"{API}/admin/invoices/{invoice['invoice_id']}/credit-notes", json={"taxable_amount": 1, "reason": "too much"})).status_code == 409


async def test_credits_cannot_add_up_to_more_than_the_invoice(client, who, send_event):
    invoice = await _issued(client, who, send_event)
    who.billing()
    over = await client.post(f"{API}/admin/invoices/{invoice['invoice_id']}/credit-notes", json={"taxable_amount": 100_000_001, "reason": "Too much"})
    assert over.status_code == 409 and over.json()["code"] == "CREDIT_EXCEEDS_INVOICE"


async def test_a_credit_against_a_paid_invoice_shows_the_refund_due(client, who, send_event):
    invoice = await _issued(client, who, send_event)
    who.billing()
    await client.post(f"{API}/admin/invoices/{invoice['invoice_id']}/payments/manual", json={"amount": 118_000_000, "reference": "UTR 1"})
    await client.post(f"{API}/admin/invoices/{invoice['invoice_id']}/credit-notes", json={"taxable_amount": 10_000_000, "reason": "Goodwill"})
    detail = (await client.get(f"{API}/invoices/{invoice['invoice_id']}")).json()["invoice"]
    assert detail["status"] == "paid" and detail["refund_due"] == 11_800_000


# ---------------------------------------------------------------- employer plans
async def _plan_world(client, who, send_event) -> None:
    await seed_orgs(send_event)
    await add_price(client, who, kind="employer_plan", code="growth", name="Growth", unit_amount=5_000_000, job_posts=10, valid_days=30)
    await set_profile(client, who, EMPLOYER, {**PROFILE, "legal_name": "Acme Labs", "state": "Maharashtra", "gstin": "27ABCDE1234F1Z5"})


async def test_an_employer_admin_buys_a_plan_and_it_activates_when_the_invoice_is_paid(client, who, send_event, sessionmaker):
    await _plan_world(client, who, send_event)
    who.employer_admin()
    tiers = (await client.get(f"{API}/employer/plans/tiers")).json()["tiers"]
    assert tiers == [{"tier": "growth", "name": "Growth", "price": 5_000_000, "job_posts": 10, "valid_days": 30}]

    bought = await client.post(f"{API}/employer/plans/growth/purchase")
    assert bought.status_code == 201, bought.text
    body = bought.json()
    assert body["plan"]["status"] == "pending" and body["invoice"]["status"] == "issued" and body["invoice"]["igst"] == 900_000 and body["invoice"]["total"] == 5_900_000
    assert await _events(sessionmaker, "plan.activated") == []

    who.billing()
    await client.post(f"{API}/admin/invoices/{body['invoice']['invoice_id']}/payments/manual", json={"amount": 5_900_000, "reference": "UPI 77"})
    events = await _events(sessionmaker, "plan.activated")
    assert len(events) == 1 and events[0].payload["employer_id"] == str(EMPLOYER) and events[0].payload["tier"] == "growth" and events[0].payload["job_posts"] == 10
    who.employer_admin()
    assert (await client.get(f"{API}/employer/plans")).json()["plans"][0]["status"] == "active"


async def test_a_plan_needs_a_billing_profile_and_only_one_may_wait_for_payment(client, who, send_event):
    await seed_orgs(send_event)
    await add_price(client, who, kind="employer_plan", code="growth", name="Growth", unit_amount=5_000_000, job_posts=10, valid_days=30)
    who.employer_admin()
    missing = await client.post(f"{API}/employer/plans/growth/purchase")
    assert missing.status_code == 409 and missing.json()["code"] == "BILLING_PROFILE_MISSING"

    await set_profile(client, who, EMPLOYER, PROFILE)
    who.employer_admin()
    assert (await client.post(f"{API}/employer/plans/growth/purchase")).status_code == 201
    twice = await client.post(f"{API}/employer/plans/growth/purchase")
    assert twice.status_code == 409 and twice.json()["code"] == "PLAN_ALREADY_PENDING"
    assert (await client.post(f"{API}/employer/plans/nonexistent/purchase")).status_code == 404


async def test_only_an_employer_admin_buys_a_plan(client, who, send_event):
    await _plan_world(client, who, send_event)
    for identity in (who.recruiter, who.head, who.billing):
        identity()
        assert (await client.post(f"{API}/employer/plans/growth/purchase")).status_code == 403


async def test_voiding_the_invoice_cancels_the_pending_plan(client, who, send_event):
    await _plan_world(client, who, send_event)
    who.employer_admin()
    body = (await client.post(f"{API}/employer/plans/growth/purchase")).json()
    who.billing()
    await client.post(f"{API}/admin/invoices/{body['invoice']['invoice_id']}/void", json={"reason": "Bought by mistake"})
    who.employer_admin()
    assert (await client.get(f"{API}/employer/plans")).json()["plans"][0]["status"] == "cancelled"
    assert (await client.post(f"{API}/employer/plans/growth/purchase")).status_code == 201  # free to buy again


async def test_a_plan_that_has_run_its_term_ends_and_is_announced_once(client, who, send_event, sessionmaker, settings):
    await _plan_world(client, who, send_event)
    who.employer_admin()
    body = (await client.post(f"{API}/employer/plans/growth/purchase")).json()
    who.billing()
    await client.post(f"{API}/admin/invoices/{body['invoice']['invoice_id']}/payments/manual", json={"amount": 5_900_000, "reference": "UPI 1"})
    async with sessionmaker() as db:
        plan = (await db.execute(select(OrgPlan))).scalar_one()
        plan.ends_at = utcnow() - timedelta(days=1)
        await db.commit()
    async with sessionmaker() as db:
        assert await PlanService(db, settings).expire_ended() == 1
    async with sessionmaker() as db:
        assert await PlanService(db, settings).expire_ended() == 0
    assert len(await _events(sessionmaker, "plan.expired")) == 1
