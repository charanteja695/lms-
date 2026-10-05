from httpx import AsyncClient

from tests.conftest import TEST_COURSE_ID

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
