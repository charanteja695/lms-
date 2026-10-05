from httpx import AsyncClient
from sqlalchemy import select

from app.models.outbox_event import OutboxEvent
from tests.conftest import TEST_COURSE_ID, TEST_ORG_ID, TEST_USER_ID

REQUEST_PAYLOAD = {"course_id": str(TEST_COURSE_ID), "requested_seats": 50, "requested_term_days": 365}


async def test_cannot_request_an_unknown_course(client: AsyncClient, as_institution_head, seed_refs) -> None:
    await seed_refs()
    as_institution_head()
    response = await client.post(
        "/api/v1/course-requests", json={"course_id": "1755000000009999", "requested_seats": 10, "requested_term_days": 30}
    )
    assert response.status_code == 404
    assert response.json()["code"] == "COURSE_NOT_FOUND"


async def test_duplicate_pending_request_is_a_conflict(client: AsyncClient, as_institution_head, seed_refs) -> None:
    await seed_refs()
    as_institution_head()
    first = await client.post("/api/v1/course-requests", json=REQUEST_PAYLOAD)
    assert first.status_code == 201
    second = await client.post("/api/v1/course-requests", json=REQUEST_PAYLOAD)
    assert second.status_code == 409
    assert second.json()["code"] == "REQUEST_ALREADY_PENDING"


async def test_institution_head_cannot_see_another_organizations_request(
    client: AsyncClient, as_institution_head, seed_refs
) -> None:
    await seed_refs()
    as_institution_head(organization_id=TEST_ORG_ID)
    created = (await client.post("/api/v1/course-requests", json=REQUEST_PAYLOAD)).json()["course_request"]

    as_institution_head(organization_id=TEST_ORG_ID + 1)
    response = await client.get(f"/api/v1/course-requests/{created['course_request_id']}")
    assert response.status_code == 403


async def test_approve_creates_an_active_subscription(client: AsyncClient, as_institution_head, as_admin, seed_refs) -> None:
    await seed_refs()
    as_institution_head()
    created = (await client.post("/api/v1/course-requests", json=REQUEST_PAYLOAD)).json()["course_request"]

    as_admin()
    response = await client.post(f"/api/v1/course-requests/{created['course_request_id']}/approve", json={})
    assert response.status_code == 200, response.text
    subscription = response.json()["subscription"]
    assert subscription["status"] == "active"
    assert subscription["seats_total"] == 50
    assert subscription["organization_id"] == str(TEST_ORG_ID)

    # can't approve twice
    response = await client.post(f"/api/v1/course-requests/{created['course_request_id']}/approve", json={})
    assert response.status_code == 400
    assert response.json()["code"] == "REQUEST_NOT_PENDING"


async def test_approve_can_override_seats_and_term(client: AsyncClient, as_institution_head, as_admin, seed_refs) -> None:
    await seed_refs()
    as_institution_head()
    created = (await client.post("/api/v1/course-requests", json=REQUEST_PAYLOAD)).json()["course_request"]

    as_admin()
    response = await client.post(
        f"/api/v1/course-requests/{created['course_request_id']}/approve", json={"seats": 10, "term_days": 30}
    )
    assert response.json()["subscription"]["seats_total"] == 10


async def test_reject_records_a_reason(client: AsyncClient, as_institution_head, as_admin, seed_refs) -> None:
    await seed_refs()
    as_institution_head()
    created = (await client.post("/api/v1/course-requests", json=REQUEST_PAYLOAD)).json()["course_request"]

    as_admin()
    response = await client.post(
        f"/api/v1/course-requests/{created['course_request_id']}/reject", json={"reason": "Not licensed for this grade band"}
    )
    assert response.status_code == 200
    body = response.json()["course_request"]
    assert body["status"] == "rejected"
    assert body["decision_reason"] == "Not licensed for this grade band"

    # a rejected request can be requested again (no longer "pending")
    as_institution_head()
    response = await client.post("/api/v1/course-requests", json=REQUEST_PAYLOAD)
    assert response.status_code == 201


async def test_the_decision_event_says_who_asked_for_what(client: AsyncClient, as_institution_head, as_admin, seed_refs, app) -> None:
    """notification-service addresses the rejection from this payload alone (it never calls back)."""
    await seed_refs()
    as_institution_head()
    created = (await client.post("/api/v1/course-requests", json=REQUEST_PAYLOAD)).json()["course_request"]
    as_admin()
    await client.post(f"/api/v1/course-requests/{created['course_request_id']}/reject", json={"reason": "Out of budget"})

    async with app.state.sessionmaker() as db:
        decided = next(e for e in (await db.execute(select(OutboxEvent))).scalars() if e.event_type == "course_request.decided")
    assert decided.payload == {
        "course_request_id": created["course_request_id"],
        "organization_id": str(TEST_ORG_ID),
        "course_id": str(TEST_COURSE_ID),
        "requested_by": str(TEST_USER_ID),
        "decision": "rejected",
        "reason": "Out of budget",
    }
