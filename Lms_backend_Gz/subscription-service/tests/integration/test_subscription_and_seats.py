from httpx import AsyncClient
from sqlalchemy import select

from app.models.outbox_event import OutboxEvent
from tests.conftest import INTERNAL_HEADERS, TEST_COURSE_ID, TEST_ORG_ID

REQUEST_PAYLOAD = {"course_id": str(TEST_COURSE_ID), "requested_seats": 2, "requested_term_days": 365}


async def _approved_subscription(client: AsyncClient, as_institution_head, as_admin, seed_refs) -> dict:
    await seed_refs()
    as_institution_head()
    created = (await client.post("/api/v1/course-requests", json=REQUEST_PAYLOAD)).json()["course_request"]
    as_admin()
    response = await client.post(f"/api/v1/course-requests/{created['course_request_id']}/approve", json={})
    return response.json()["subscription"]


async def test_cancel_an_active_subscription(client: AsyncClient, as_institution_head, as_admin, seed_refs) -> None:
    subscription = await _approved_subscription(client, as_institution_head, as_admin, seed_refs)
    as_admin()
    response = await client.post(
        f"/api/v1/subscriptions/{subscription['subscription_id']}/cancel", json={"reason": "Institution requested early termination"}
    )
    assert response.status_code == 200
    assert response.json()["subscription"]["status"] == "cancelled"

    response = await client.post(
        f"/api/v1/subscriptions/{subscription['subscription_id']}/cancel", json={"reason": "Institution requested early termination"}
    )
    assert response.status_code == 400
    assert response.json()["code"] == "SUBSCRIPTION_NOT_ACTIVE"


async def test_seat_endpoints_reject_calls_without_a_valid_caller(client: AsyncClient, as_institution_head, as_admin, seed_refs) -> None:
    subscription = await _approved_subscription(client, as_institution_head, as_admin, seed_refs)
    response = await client.post(
        f"/api/v1/subscriptions/{subscription['subscription_id']}/seats/reserve", json={"reservation_key": "enrolment-1"}
    )
    assert response.status_code == 401


async def test_seat_reserve_and_release_round_trip(client: AsyncClient, as_institution_head, as_admin, seed_refs) -> None:
    subscription = await _approved_subscription(client, as_institution_head, as_admin, seed_refs)
    sub_id = subscription["subscription_id"]

    response = await client.post(
        f"/api/v1/subscriptions/{sub_id}/seats/reserve", json={"reservation_key": "enrolment-1"}, headers=INTERNAL_HEADERS
    )
    assert response.status_code == 200
    assert response.json()["seats"] == {"seats_total": 2, "seats_used": 1, "seats_available": 1}

    response = await client.post(
        f"/api/v1/subscriptions/{sub_id}/seats/release", json={"reservation_key": "enrolment-1"}, headers=INTERNAL_HEADERS
    )
    assert response.json()["seats"]["seats_used"] == 0


async def test_seat_reserve_is_idempotent_on_reservation_key(client: AsyncClient, as_institution_head, as_admin, seed_refs) -> None:
    subscription = await _approved_subscription(client, as_institution_head, as_admin, seed_refs)
    sub_id = subscription["subscription_id"]

    await client.post(f"/api/v1/subscriptions/{sub_id}/seats/reserve", json={"reservation_key": "enrolment-1"}, headers=INTERNAL_HEADERS)
    response = await client.post(
        f"/api/v1/subscriptions/{sub_id}/seats/reserve", json={"reservation_key": "enrolment-1"}, headers=INTERNAL_HEADERS
    )
    assert response.json()["seats"]["seats_used"] == 1  # not double-counted


async def test_seat_reserve_fails_once_full(client: AsyncClient, as_institution_head, as_admin, seed_refs) -> None:
    subscription = await _approved_subscription(client, as_institution_head, as_admin, seed_refs)  # 2 seats
    sub_id = subscription["subscription_id"]

    await client.post(f"/api/v1/subscriptions/{sub_id}/seats/reserve", json={"reservation_key": "enrolment-1"}, headers=INTERNAL_HEADERS)
    await client.post(f"/api/v1/subscriptions/{sub_id}/seats/reserve", json={"reservation_key": "enrolment-2"}, headers=INTERNAL_HEADERS)
    response = await client.post(
        f"/api/v1/subscriptions/{sub_id}/seats/reserve", json={"reservation_key": "enrolment-3"}, headers=INTERNAL_HEADERS
    )
    assert response.status_code == 400
    assert response.json()["code"] == "NO_SEATS_AVAILABLE"


async def test_release_is_idempotent_when_never_reserved(client: AsyncClient, as_institution_head, as_admin, seed_refs) -> None:
    subscription = await _approved_subscription(client, as_institution_head, as_admin, seed_refs)
    response = await client.post(
        f"/api/v1/subscriptions/{subscription['subscription_id']}/seats/release",
        json={"reservation_key": "never-reserved"},
        headers=INTERNAL_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["seats"]["seats_used"] == 0


async def test_the_cancellation_event_names_the_institution_and_course(
    client: AsyncClient, as_institution_head, as_admin, seed_refs, app
) -> None:
    subscription = await _approved_subscription(client, as_institution_head, as_admin, seed_refs)
    as_admin()
    await client.post(f"/api/v1/subscriptions/{subscription['subscription_id']}/cancel", json={"reason": "Non-payment"})

    async with app.state.sessionmaker() as db:
        cancelled = next(e for e in (await db.execute(select(OutboxEvent))).scalars() if e.event_type == "subscription.cancelled")
    assert cancelled.payload == {
        "subscription_id": subscription["subscription_id"],
        "organization_id": str(TEST_ORG_ID),
        "course_id": str(TEST_COURSE_ID),
        "reason": "Non-payment",
    }
