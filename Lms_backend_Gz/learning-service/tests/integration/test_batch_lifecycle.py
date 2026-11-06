from httpx import AsyncClient

from tests.conftest import TEST_COURSE_ID, TEST_ORG_ID, TEST_SUBSCRIPTION_ID

BATCH_PAYLOAD = {"course_id": str(TEST_COURSE_ID), "name": "2026 Batch A"}


async def test_create_batch_requires_an_active_entitlement(client: AsyncClient, as_institution_head, seed_institution, seed_course) -> None:
    await seed_institution()
    await seed_course()
    as_institution_head()
    response = await client.post("/api/v1/batches", json=BATCH_PAYLOAD)
    assert response.status_code == 400
    assert response.json()["code"] == "NO_ACTIVE_SUBSCRIPTION"


async def test_create_batch_succeeds_with_an_entitlement(
    client: AsyncClient, as_institution_head, seed_institution, seed_course, seed_entitlement
) -> None:
    await seed_institution()
    await seed_course()
    await seed_entitlement()
    as_institution_head()
    response = await client.post("/api/v1/batches", json=BATCH_PAYLOAD)
    assert response.status_code == 201, response.text
    batch = response.json()["batch"]
    assert batch["organization_id"] == str(TEST_ORG_ID)
    assert batch["subscription_id"] == str(TEST_SUBSCRIPTION_ID)
    assert batch["status"] == "active"
    assert batch["course_id"] == str(TEST_COURSE_ID)
    assert batch["title"] == "A Course"  # from the course.published payload, for display only

    # A fresh GET (not the create response's in-memory shortcut) resolves the title the same way.
    fetched = (await client.get(f"/api/v1/batches/{batch['batch_id']}")).json()["batch"]
    assert fetched["course_id"] == str(TEST_COURSE_ID) and fetched["title"] == "A Course"


async def test_institution_head_cannot_see_another_organizations_batch(
    client: AsyncClient, as_institution_head, seed_institution, seed_course, seed_entitlement
) -> None:
    await seed_institution()
    await seed_course()
    await seed_entitlement()
    as_institution_head(organization_id=TEST_ORG_ID)
    created = (await client.post("/api/v1/batches", json=BATCH_PAYLOAD)).json()["batch"]

    as_institution_head(organization_id=TEST_ORG_ID + 1)
    response = await client.get(f"/api/v1/batches/{created['batch_id']}")
    assert response.status_code == 403


async def test_retired_course_cannot_start_a_new_batch(client: AsyncClient, app, as_institution_head, seed_institution, seed_course, seed_entitlement) -> None:
    await seed_institution()
    payload = await seed_course()
    await seed_entitlement()

    from app.services.course_structure_service import CourseStructureService

    async with app.state.sessionmaker() as db:
        await CourseStructureService(db).mark_retired(payload)
        await db.commit()

    as_institution_head()
    response = await client.post("/api/v1/batches", json=BATCH_PAYLOAD)
    assert response.status_code == 404
    assert response.json()["code"] == "COURSE_NOT_AVAILABLE"
