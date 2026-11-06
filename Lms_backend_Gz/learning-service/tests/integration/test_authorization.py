from httpx import AsyncClient

from tests.conftest import TEST_COURSE_ID, TEST_ORG_ID, TEST_USER_ID

BATCH_PAYLOAD = {"course_id": str(TEST_COURSE_ID), "name": "2026 Batch A"}


async def test_missing_token_is_rejected_without_any_network_call(client: AsyncClient) -> None:
    response = await client.post("/api/v1/batches", json=BATCH_PAYLOAD)
    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_student_cannot_create_a_batch(client: AsyncClient, as_student) -> None:
    as_student(user_id=1)
    response = await client.post("/api/v1/batches", json=BATCH_PAYLOAD)
    assert response.status_code == 403


async def test_institution_head_without_organization_is_rejected(client: AsyncClient, authed) -> None:
    authed(role="institution_head", organization_id=None)
    response = await client.post("/api/v1/batches", json=BATCH_PAYLOAD)
    assert response.status_code == 403


async def test_admin_requires_an_explicit_organization_id(client: AsyncClient, as_admin, seed_institution, seed_course) -> None:
    await seed_institution()
    await seed_course()
    as_admin()
    response = await client.post("/api/v1/batches", json=BATCH_PAYLOAD)
    assert response.status_code == 400
    assert response.json()["code"] == "ORGANIZATION_ID_REQUIRED"


async def test_batches_follow_the_persons_permissions(client, authed):
    """A super admin can let one staff member manage batches, or stop a head; a student never sees the batch list."""
    authed(role="student", organization_id=TEST_ORG_ID, user_id=TEST_USER_ID)
    assert (await client.get("/api/v1/batches")).status_code == 403
    authed(role="staff", organization_id=TEST_ORG_ID)
    assert (await client.get("/api/v1/batches")).status_code == 200
    authed(role="institution_head", organization_id=TEST_ORG_ID, defaults=False)
    assert (await client.get("/api/v1/batches")).status_code == 403
    authed(role="student", organization_id=TEST_ORG_ID, defaults=False)
    assert (await client.get("/api/v1/enrollments")).status_code == 403


async def test_a_removed_matrix_cell_stops_that_one_action(client, authed, seed_institution, seed_course, seed_entitlement):
    """A head the super admin left View + Revoke on Batches (but not Create): listing works, creating is refused,
    although the coarse learning.batches.manage key is still in the token."""
    await seed_institution()
    await seed_course()
    await seed_entitlement()
    authed(role="institution_head", organization_id=TEST_ORG_ID, defaults=False,
           scopes=("batches.view", "batches.revoke", "learning.batches.view", "learning.batches.manage"))
    assert (await client.get("/api/v1/batches")).status_code == 200
    refused = await client.post("/api/v1/batches", json={"course_id": str(TEST_COURSE_ID), "name": "Morning batch"})
    assert refused.status_code == 403
    authed(role="institution_head", organization_id=TEST_ORG_ID)
    assert (await client.post("/api/v1/batches", json={"course_id": str(TEST_COURSE_ID), "name": "Morning batch"})).status_code == 201
