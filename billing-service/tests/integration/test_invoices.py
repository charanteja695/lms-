"""Invoices: drafted from subscription-service's event, edited by a billing manager, issued with a gap-free number and a frozen tax split,
never changed after (docs/PRODUCT.md §5.10)."""

from sqlalchemy import select

from app.models.outbox_event import OutboxEvent
from tests.conftest import (
    API,
    COURSE_PY,
    COURSE_SQL,
    INSTITUTION,
    INSTITUTION_2,
    PROFILE,
    PROFILE_OTHER_STATE,
    activate_subscription,
    add_price,
    first_draft,
    seed_orgs,
    set_profile,
)


async def _draft(client, who, send_event, *, profile=PROFILE, seats: int = 100) -> dict:
    await seed_orgs(send_event)
    await add_price(client, who)
    if profile is not None:
        await set_profile(client, who, INSTITUTION, profile)
    await activate_subscription(send_event, seats=seats)
    return await first_draft(client, who)


async def test_an_activated_subscription_drafts_an_invoice_at_the_price_list_price(client, who, send_event):
    draft = await _draft(client, who, send_event)
    assert draft["status"] == "draft" and draft["number"] is None and draft["organization_id"] == str(INSTITUTION)
    assert draft["subtotal"] == 100_000_000 and draft["total"] == 118_000_000 and (draft["cgst"], draft["sgst"], draft["igst"]) == (9_000_000, 9_000_000, 0)


async def test_the_same_subscription_never_makes_two_invoices(client, who, send_event):
    await seed_orgs(send_event)
    await add_price(client, who)
    await activate_subscription(send_event, subscription="1755000000212001")
    await activate_subscription(send_event, subscription="1755000000212001")  # a different event id, the same subscription
    who.billing()
    assert (await client.get(f"{API}/invoices")).json()["page_context"]["total_records"] == 1


async def test_a_course_without_a_price_drafts_a_zero_invoice_with_a_note_that_cannot_be_issued(client, who, send_event):
    await seed_orgs(send_event)
    await set_profile(client, who, INSTITUTION, PROFILE)
    await activate_subscription(send_event, course=COURSE_SQL)
    draft = await first_draft(client, who)
    assert draft["total"] == 0 and "No price configured" in draft["note"]
    who.billing()
    refused = await client.post(f"{API}/admin/invoices/{draft['invoice_id']}/issue")
    assert refused.status_code == 409 and refused.json()["code"] == "INVOICE_EMPTY"

    fixed = await client.put(
        f"{API}/admin/invoices/{draft['invoice_id']}", json={"lines": [{"description": "SQL for Data - 100 seats", "quantity": 1, "unit_amount": 50_000_000}], "discount": 0, "note": None}
    )
    assert fixed.status_code == 200 and fixed.json()["invoice"]["subtotal"] == 50_000_000
    assert (await client.post(f"{API}/admin/invoices/{draft['invoice_id']}/issue")).status_code == 200


async def test_an_accepted_quote_fixes_the_price_and_its_discount_carries_over(client, who, send_event):
    await seed_orgs(send_event)
    await add_price(client, who)
    await set_profile(client, who, INSTITUTION, PROFILE)
    who.head()
    quote_id = (await client.post(f"{API}/quotes", json={"lines": [{"course_id": str(COURSE_PY), "seats": 100, "term_days": 365}]})).json()["quote"]["quote_id"]
    who.billing()
    await client.post(f"{API}/admin/quotes/{quote_id}/discount", json={"amount": 10_000_000, "note": "Launch offer"})
    who.head()
    await client.post(f"{API}/quotes/{quote_id}/accept")
    who.billing()
    price = (await client.get(f"{API}/admin/prices")).json()["prices"][0]
    await client.patch(f"{API}/admin/prices/{price['price_id']}", json={"unit_amount": 2_000_000})  # the list price doubles after the quote was accepted

    await activate_subscription(send_event, seats=100)
    draft = await first_draft(client, who)
    assert draft["subtotal"] == 100_000_000 and draft["discount"] == 10_000_000 and draft["taxable"] == 90_000_000  # the quoted price, not the new one
    assert draft["total"] == 106_200_000


async def test_the_customer_never_sees_a_draft(client, who, send_event):
    draft = await _draft(client, who, send_event)
    who.head()
    assert (await client.get(f"{API}/invoices")).json()["invoices"] == []
    assert (await client.get(f"{API}/invoices/{draft['invoice_id']}")).status_code == 404


async def test_issuing_numbers_the_invoice_freezes_the_customer_and_splits_the_tax_by_state(client, who, send_event):
    draft = await _draft(client, who, send_event)
    who.billing()
    issued = await client.post(f"{API}/admin/invoices/{draft['invoice_id']}/issue")
    assert issued.status_code == 200, issued.text
    invoice = issued.json()["invoice"]
    assert invoice["status"] == "issued" and invoice["number"].startswith("INV/") and invoice["number"].endswith("/000001")
    assert invoice["customer"]["legal_name"] == "Anna University" and invoice["place_of_supply"] == "Karnataka" and invoice["balance_due"] == 118_000_000
    assert invoice["seller"]["state"] == "Karnataka" and invoice["due_date"] is not None
    assert [line["sac_code"] for line in invoice["lines"]] == ["998439"]

    who.head()  # the customer now sees it
    assert (await client.get(f"{API}/invoices/{invoice['invoice_id']}")).status_code == 200
    who.head(organization_id=INSTITUTION_2)
    assert (await client.get(f"{API}/invoices/{invoice['invoice_id']}")).status_code == 404


async def test_an_out_of_state_customer_is_charged_igst(client, who, send_event):
    await seed_orgs(send_event)
    await add_price(client, who)
    await set_profile(client, who, INSTITUTION, PROFILE_OTHER_STATE)
    await activate_subscription(send_event)
    draft = await first_draft(client, who)
    assert (draft["cgst"], draft["sgst"], draft["igst"]) == (0, 0, 18_000_000)


async def test_issuing_needs_a_billing_profile(client, who, send_event):
    draft = await _draft(client, who, send_event, profile=None)
    assert draft["cgst"] == draft["igst"] == 0  # no state known yet, so no tax shown
    who.billing()
    refused = await client.post(f"{API}/admin/invoices/{draft['invoice_id']}/issue")
    assert refused.status_code == 409 and refused.json()["code"] == "BILLING_PROFILE_MISSING"
    await set_profile(client, who, INSTITUTION, PROFILE)
    assert (await client.post(f"{API}/admin/invoices/{draft['invoice_id']}/issue")).json()["invoice"]["total"] == 118_000_000


async def test_numbers_are_sequential_and_an_issued_invoice_never_changes(client, who, send_event):
    await seed_orgs(send_event)
    await add_price(client, who)
    await set_profile(client, who, INSTITUTION, PROFILE)
    numbers = []
    for n in range(3):
        await activate_subscription(send_event, subscription=str(1755000000213000 + n))
    who.billing()
    for invoice in (await client.get(f"{API}/invoices", params={"status": "draft"})).json()["invoices"]:
        numbers.append((await client.post(f"{API}/admin/invoices/{invoice['invoice_id']}/issue")).json()["invoice"]["number"])
    assert sorted(n.rsplit("/", 1)[1] for n in numbers) == ["000001", "000002", "000003"]

    edit = await client.put(f"{API}/admin/invoices/{invoice['invoice_id']}", json={"lines": [{"description": "Changed", "quantity": 1, "unit_amount": 1}], "discount": 0, "note": None})
    assert edit.status_code == 409 and edit.json()["code"] == "INVOICE_NOT_DRAFT"
    again = await client.post(f"{API}/admin/invoices/{invoice['invoice_id']}/issue")
    assert again.status_code == 409


async def test_only_a_billing_manager_edits_issues_or_voids(client, who, send_event):
    draft = await _draft(client, who, send_event)
    for call in (
        lambda: client.put(f"{API}/admin/invoices/{draft['invoice_id']}", json={"lines": [{"description": "x", "quantity": 1, "unit_amount": 1}], "discount": 0}),
        lambda: client.post(f"{API}/admin/invoices/{draft['invoice_id']}/issue"),
        lambda: client.post(f"{API}/admin/invoices/{draft['invoice_id']}/void", json={"reason": "no"}),
    ):
        who.head()
        assert (await call()).status_code == 403
        who.other_admin()
        assert (await call()).status_code == 403


async def test_an_unpaid_invoice_can_be_voided_with_a_reason(client, who, send_event):
    draft = await _draft(client, who, send_event)
    who.billing()
    await client.post(f"{API}/admin/invoices/{draft['invoice_id']}/issue")
    voided = await client.post(f"{API}/admin/invoices/{draft['invoice_id']}/void", json={"reason": "Raised against the wrong course"})
    assert voided.status_code == 200 and voided.json()["invoice"]["status"] == "void"
    assert (await client.post(f"{API}/admin/invoices/{draft['invoice_id']}/void", json={"reason": "again"})).status_code == 409


async def test_issuing_announces_invoice_issued_with_the_fields_analytics_reads(client, who, send_event, sessionmaker):
    draft = await _draft(client, who, send_event)
    who.billing()
    await client.post(f"{API}/admin/invoices/{draft['invoice_id']}/issue")
    async with sessionmaker() as db:
        event = (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == "invoice.issued"))).scalar_one()
    assert event.payload["organization_id"] == str(INSTITUTION) and event.payload["total_amount"] == 118_000_000 and event.payload["number"].startswith("INV/")


async def test_an_invoice_for_the_overdue_sweep(client, who, send_event, sessionmaker, settings):
    from datetime import timedelta

    from app.core.time import utcnow
    from app.models.billing import Invoice
    from app.services.invoice_service import InvoiceService

    draft = await _draft(client, who, send_event)
    who.billing()
    await client.post(f"{API}/admin/invoices/{draft['invoice_id']}/issue")
    async with sessionmaker() as db:
        invoice = (await db.execute(select(Invoice))).scalar_one()
        invoice.due_date = utcnow().date() - timedelta(days=1)
        await db.commit()
    async with sessionmaker() as db:
        assert await InvoiceService(db, settings).flag_overdue() == 1
    async with sessionmaker() as db:
        assert await InvoiceService(db, settings).flag_overdue() == 0  # once
    assert (await client.get(f"{API}/invoices/{draft['invoice_id']}")).json()["invoice"]["status"] == "overdue"
