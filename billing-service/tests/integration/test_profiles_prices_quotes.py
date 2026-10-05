"""Billing profiles, the price list and quotes (docs/PRODUCT.md §5.10)."""

from datetime import timedelta

from sqlalchemy import select

from app.core.time import utcnow
from app.models.billing import Quote
from app.services.quote_service import QuoteService
from tests.conftest import (
    API,
    COURSE_PY,
    COURSE_SQL,
    INSTITUTION,
    INSTITUTION_2,
    PROFILE,
    PROFILE_OTHER_STATE,
    add_price,
    seed_orgs,
    set_profile,
)


async def test_an_institution_head_sets_their_own_billing_profile(client, who, send_event):
    await seed_orgs(send_event)
    who.head()
    saved = await client.put(f"{API}/billing-profile", json=PROFILE)
    assert saved.status_code == 200, saved.text
    assert saved.json()["profile"]["organization_id"] == str(INSTITUTION) and saved.json()["profile"]["state"] == "Karnataka"
    assert (await client.get(f"{API}/billing-profile")).json()["profile"]["legal_name"] == "Anna University"


async def test_a_gstin_of_the_wrong_shape_is_refused(client, who, send_event):
    await seed_orgs(send_event)
    who.head()
    response = await client.put(f"{API}/billing-profile", json={**PROFILE, "gstin": "NOT-A-GSTIN0000"})
    assert response.status_code == 422 and response.json()["details"][0]["code"] == "INVALID_GSTIN"


async def test_staff_and_other_institutions_cannot_touch_a_profile(client, who, send_event):
    await seed_orgs(send_event)
    who.staff()
    assert (await client.put(f"{API}/billing-profile", json=PROFILE)).status_code == 403
    who.head(organization_id=INSTITUTION_2)
    assert (await client.get(f"{API}/admin/organizations/{INSTITUTION}/billing-profile")).status_code == 403


async def test_a_billing_manager_sets_any_organisations_profile(client, who, send_event):
    await seed_orgs(send_event)
    await set_profile(client, who, INSTITUTION_2, PROFILE_OTHER_STATE)
    who.head(organization_id=INSTITUTION_2)
    assert (await client.get(f"{API}/billing-profile")).json()["profile"]["state"] == "Tamil Nadu"


async def test_a_profile_for_an_organisation_nobody_has_heard_of_is_refused(client, who):
    who.billing()
    response = await client.put(f"{API}/admin/organizations/1755000000299999/billing-profile", json=PROFILE)
    assert response.status_code == 404


async def test_prices_are_managed_by_billing_and_read_by_organisations(client, who):
    price = await add_price(client, who)
    duplicate = await client.post(f"{API}/admin/prices", json={"kind": "course_seat", "code": str(COURSE_PY), "name": "Again", "unit_amount": 5})
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "PRICE_EXISTS"

    who.head()
    listed = (await client.get(f"{API}/prices")).json()["prices"]
    assert [p["code"] for p in listed] == [str(COURSE_PY)]
    assert (await client.post(f"{API}/admin/prices", json={"kind": "course_seat", "code": "x", "name": "Nope", "unit_amount": 1})).status_code == 403

    who.billing()
    await client.patch(f"{API}/admin/prices/{price['price_id']}", json={"active": False})
    who.head()
    assert (await client.get(f"{API}/prices")).json()["prices"] == []


async def test_an_employer_plan_price_needs_its_allowance(client, who):
    who.billing()
    missing = await client.post(f"{API}/admin/prices", json={"kind": "employer_plan", "code": "growth", "name": "Growth", "unit_amount": 500_000})
    assert missing.status_code == 422
    ok = await client.post(f"{API}/admin/prices", json={"kind": "employer_plan", "code": "growth", "name": "Growth", "unit_amount": 500_000, "job_posts": 10, "valid_days": 30})
    assert ok.status_code == 201 and ok.json()["price"]["meta"] == {"job_posts": 10, "valid_days": 30}


async def test_a_quote_prices_seats_over_the_term_and_adds_gst_by_state(client, who, send_event):
    await seed_orgs(send_event)
    await add_price(client, who)
    await set_profile(client, who, INSTITUTION, PROFILE)  # Karnataka = the seller's state: CGST+SGST, same 18% in total
    who.head()
    created = await client.post(f"{API}/quotes", json={"lines": [{"course_id": str(COURSE_PY), "seats": 100, "term_days": 365}]})
    assert created.status_code == 201, created.text
    quote = created.json()["quote"]
    assert quote["subtotal"] == 100_000_000 and quote["gst"] == 18_000_000 and quote["total"] == 118_000_000 and quote["status"] == "open"


async def test_a_course_with_no_price_cannot_be_quoted(client, who, send_event):
    await seed_orgs(send_event)
    who.head()
    response = await client.post(f"{API}/quotes", json={"lines": [{"course_id": str(COURSE_SQL), "seats": 10, "term_days": 365}]})
    assert response.status_code == 422 and response.json()["details"][0]["code"] == "NO_PRICE"


async def test_a_discount_lowers_the_taxable_amount_and_so_the_gst(client, who, send_event):
    await seed_orgs(send_event)
    await add_price(client, who)
    who.head()
    quote = (await client.post(f"{API}/quotes", json={"lines": [{"course_id": str(COURSE_PY), "seats": 100, "term_days": 365}]})).json()["quote"]
    who.head()
    assert (await client.post(f"{API}/admin/quotes/{quote['quote_id']}/discount", json={"amount": 10_000_000, "note": "Launch offer"})).status_code == 403
    who.billing()
    discounted = await client.post(f"{API}/admin/quotes/{quote['quote_id']}/discount", json={"amount": 10_000_000, "note": "Launch offer"})
    assert discounted.status_code == 200, discounted.text
    body = discounted.json()["quote"]
    assert body["discount"] == 10_000_000 and body["gst"] == 16_200_000 and body["total"] == 106_200_000  # IGST case: no profile yet, 18% of 90,000,000


async def test_accepting_a_quote_is_only_for_its_own_organisation_and_only_once(client, who, send_event):
    await seed_orgs(send_event)
    await add_price(client, who)
    who.head()
    quote_id = (await client.post(f"{API}/quotes", json={"lines": [{"course_id": str(COURSE_PY), "seats": 10, "term_days": 365}]})).json()["quote"]["quote_id"]
    who.head(organization_id=INSTITUTION_2)
    assert (await client.post(f"{API}/quotes/{quote_id}/accept")).status_code == 404
    who.head()
    assert (await client.post(f"{API}/quotes/{quote_id}/accept")).json()["quote"]["status"] == "accepted"
    again = await client.post(f"{API}/quotes/{quote_id}/accept")
    assert again.status_code == 409 and again.json()["code"] == "QUOTE_NOT_OPEN"


async def test_an_expired_quote_cannot_be_accepted_and_the_sweep_expires_stale_ones(client, who, send_event, sessionmaker, settings):
    await seed_orgs(send_event)
    await add_price(client, who)
    who.head()
    first = (await client.post(f"{API}/quotes", json={"lines": [{"course_id": str(COURSE_PY), "seats": 10, "term_days": 365}]})).json()["quote"]["quote_id"]
    second = (await client.post(f"{API}/quotes", json={"lines": [{"course_id": str(COURSE_PY), "seats": 20, "term_days": 365}]})).json()["quote"]["quote_id"]
    async with sessionmaker() as db:
        for quote in (await db.execute(select(Quote))).scalars():
            quote.valid_until = utcnow() - timedelta(days=1)
        await db.commit()

    expired = await client.post(f"{API}/quotes/{first}/accept")
    assert expired.status_code == 409 and expired.json()["code"] == "QUOTE_EXPIRED"
    async with sessionmaker() as db:
        assert await QuoteService(db, settings).expire_stale() == 1  # the other open one
    assert (await client.get(f"{API}/quotes/{second}")).json()["quote"]["status"] == "expired"
