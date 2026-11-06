from httpx import AsyncClient
from sqlalchemy import select

from app.models.outbox_event import OutboxEvent
from tests.conftest import TEST_COURSE_ID, TEST_VERSION_ID

BATCH_PAYLOAD = {"course_id": str(TEST_COURSE_ID), "name": "2026 Batch A"}
STUDENT_ID = 1755000000005999


async def _batch(client: AsyncClient, as_institution_head, seed_institution, seed_course, seed_entitlement) -> dict:
    await seed_institution()
    await seed_course()
    await seed_entitlement()
    as_institution_head()
    return (await client.post("/api/v1/batches", json=BATCH_PAYLOAD)).json()["batch"]


async def test_enroll_reserves_a_seat_and_creates_the_enrolment(
    client: AsyncClient, as_institution_head, seed_institution, seed_course, seed_entitlement, mock_seats
) -> None:
    batch = await _batch(client, as_institution_head, seed_institution, seed_course, seed_entitlement)
    as_institution_head()
    response = await client.post(f"/api/v1/batches/{batch['batch_id']}/enrollments", json={"student_user_id": str(STUDENT_ID)})
    assert response.status_code == 201, response.text
    enrollment = response.json()["enrollment"]
    assert enrollment["status"] == "active"
    assert enrollment["student_user_id"] == str(STUDENT_ID)
    assert mock_seats.calls.last.request.url.path.endswith("/reserve")


async def test_enroll_when_subscription_service_rejects_the_seat_creates_no_enrollment(
    client: AsyncClient, as_institution_head, seed_institution, seed_course, seed_entitlement, mock_seats
) -> None:
    from httpx import Response

    mock_seats.post(url__regex=r"/api/v1/subscriptions/\d+/seats/reserve").mock(
        return_value=Response(400, json={"status": "error", "code": "NO_SEATS_AVAILABLE", "message": "No seats left."})
    )
    batch = await _batch(client, as_institution_head, seed_institution, seed_course, seed_entitlement)
    as_institution_head()
    response = await client.post(f"/api/v1/batches/{batch['batch_id']}/enrollments", json={"student_user_id": str(STUDENT_ID)})
    assert response.status_code == 400
    assert response.json()["code"] == "NO_SEATS_AVAILABLE"

    list_response = await client.get("/api/v1/enrollments", params={"batch_id": batch["batch_id"]})
    assert list_response.json()["page_context"]["total_records"] == 0


async def test_double_active_enrollment_is_a_conflict(
    client: AsyncClient, as_institution_head, seed_institution, seed_course, seed_entitlement, mock_seats
) -> None:
    batch = await _batch(client, as_institution_head, seed_institution, seed_course, seed_entitlement)
    as_institution_head()
    await client.post(f"/api/v1/batches/{batch['batch_id']}/enrollments", json={"student_user_id": str(STUDENT_ID)})
    response = await client.post(f"/api/v1/batches/{batch['batch_id']}/enrollments", json={"student_user_id": str(STUDENT_ID)})
    assert response.status_code == 409


async def test_withdraw_releases_the_seat(
    client: AsyncClient, as_institution_head, seed_institution, seed_course, seed_entitlement, mock_seats
) -> None:
    batch = await _batch(client, as_institution_head, seed_institution, seed_course, seed_entitlement)
    as_institution_head()
    enrollment = (
        await client.post(f"/api/v1/batches/{batch['batch_id']}/enrollments", json={"student_user_id": str(STUDENT_ID)})
    ).json()["enrollment"]

    response = await client.post(f"/api/v1/enrollments/{enrollment['enrollment_id']}/withdraw")
    assert response.status_code == 200
    assert response.json()["enrollment"]["status"] == "withdrawn"
    assert mock_seats.calls.last.request.url.path.endswith("/release")


async def test_only_the_enrolled_student_can_complete_their_own_item(
    client: AsyncClient, as_institution_head, as_student, seed_institution, seed_course, seed_entitlement, mock_seats
) -> None:
    batch = await _batch(client, as_institution_head, seed_institution, seed_course, seed_entitlement)
    as_institution_head()
    enrollment = (
        await client.post(f"/api/v1/batches/{batch['batch_id']}/enrollments", json={"student_user_id": str(STUDENT_ID)})
    ).json()["enrollment"]

    as_student(user_id=STUDENT_ID + 1)  # a different student
    response = await client.post(f"/api/v1/enrollments/{enrollment['enrollment_id']}/items/1755000000005301/complete")
    assert response.status_code == 403

    as_student(user_id=STUDENT_ID)
    response = await client.post(f"/api/v1/enrollments/{enrollment['enrollment_id']}/items/1755000000005301/complete")
    assert response.status_code == 201

    # idempotent: completing the same item again is a no-op, not an error
    response = await client.post(f"/api/v1/enrollments/{enrollment['enrollment_id']}/items/1755000000005301/complete")
    assert response.status_code == 201


async def test_unlock_state_reflects_completed_items_and_final_eligibility(
    client: AsyncClient, as_institution_head, as_student, seed_institution, seed_course, seed_entitlement, mock_seats
) -> None:
    batch = await _batch(client, as_institution_head, seed_institution, seed_course, seed_entitlement)
    as_institution_head()
    enrollment = (
        await client.post(f"/api/v1/batches/{batch['batch_id']}/enrollments", json={"student_user_id": str(STUDENT_ID)})
    ).json()["enrollment"]

    as_student(user_id=STUDENT_ID)
    state = (await client.get(f"/api/v1/enrollments/{enrollment['enrollment_id']}/unlock-state")).json()["unlock_state"]
    assert state["eligible_for_final"] is False
    assert state["modules"][0]["title"] == "Module One"
    assert state["modules"][0]["topics"][0]["unlocked"] is True
    assert state["modules"][0]["topics"][0]["completed"] is False
    assert state["modules"][0]["topics"][0]["title"] == "Topic One"
    items = state["modules"][0]["topics"][0]["items"]
    assert [item["title"] for item in items] == ["Intro video", "Notes"]
    assert all(item["completed"] is False for item in items)

    await client.post(f"/api/v1/enrollments/{enrollment['enrollment_id']}/items/1755000000005301/complete")
    await client.post(f"/api/v1/enrollments/{enrollment['enrollment_id']}/items/1755000000005302/complete")

    state = (await client.get(f"/api/v1/enrollments/{enrollment['enrollment_id']}/unlock-state")).json()["unlock_state"]
    assert state["modules"][0]["topics"][0]["completed"] is True
    assert state["modules"][0]["completed"] is True
    assert state["eligible_for_final"] is True
    assert all(item["completed"] is True for item in state["modules"][0]["topics"][0]["items"])


async def test_events_name_the_student_so_notification_service_can_address_them(
    client: AsyncClient, as_institution_head, as_student, seed_institution, seed_course, seed_entitlement, mock_seats, app
) -> None:
    batch = await _batch(client, as_institution_head, seed_institution, seed_course, seed_entitlement)
    as_institution_head()
    enrollment = (
        await client.post(f"/api/v1/batches/{batch['batch_id']}/enrollments", json={"student_user_id": str(STUDENT_ID)})
    ).json()["enrollment"]
    as_student(user_id=STUDENT_ID)
    await client.post(f"/api/v1/enrollments/{enrollment['enrollment_id']}/items/1755000000005301/complete")
    await client.post(f"/api/v1/enrollments/{enrollment['enrollment_id']}/items/1755000000005302/complete")
    as_institution_head()
    await client.post(f"/api/v1/enrollments/{enrollment['enrollment_id']}/withdraw")

    async with app.state.sessionmaker() as db:
        events = {e.event_type: e.payload for e in (await db.execute(select(OutboxEvent))).scalars()}
    assert events["course.eligible_for_final"]["student_user_id"] == str(STUDENT_ID)
    assert events["course.eligible_for_final"]["version_id"] == str(TEST_VERSION_ID)
    assert events["enrollment.removed"]["student_user_id"] == str(STUDENT_ID)
    assert events["enrollment.removed"]["version_id"] == str(TEST_VERSION_ID)


async def test_a_student_reads_only_the_batch_they_are_enrolled_in(
    client: AsyncClient, as_institution_head, as_student, seed_institution, seed_course, seed_entitlement, mock_seats
) -> None:
    batch = await _batch(client, as_institution_head, seed_institution, seed_course, seed_entitlement)
    other = (await client.post("/api/v1/batches", json={**BATCH_PAYLOAD, "name": "2026 Batch B"})).json()["batch"]
    await client.post(f"/api/v1/batches/{batch['batch_id']}/enrollments", json={"student_user_id": str(STUDENT_ID)})

    as_student(user_id=STUDENT_ID)
    mine = await client.get(f"/api/v1/batches/{batch['batch_id']}")
    assert mine.status_code == 200, mine.text
    assert mine.json()["batch"]["title"]
    assert (await client.get(f"/api/v1/batches/{other['batch_id']}")).status_code == 403
    as_student(user_id=STUDENT_ID + 1)
    assert (await client.get(f"/api/v1/batches/{batch['batch_id']}")).status_code == 403
