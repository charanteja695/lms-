from httpx import AsyncClient

REQUEST_PAYLOAD = {"course_id": "1755000000004555", "requested_seats": 50, "requested_term_days": 365}


async def test_missing_token_is_rejected_without_any_network_call(client: AsyncClient) -> None:
    response = await client.post("/api/v1/course-requests", json=REQUEST_PAYLOAD)
    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_admin_cannot_submit_a_course_request(client: AsyncClient, as_admin) -> None:
    as_admin()
    response = await client.post("/api/v1/course-requests", json=REQUEST_PAYLOAD)
    assert response.status_code == 403


async def test_institution_head_without_organization_is_rejected(client: AsyncClient, authed) -> None:
    authed(role="institution_head", organization_id=None)
    response = await client.post("/api/v1/course-requests", json=REQUEST_PAYLOAD)
    assert response.status_code == 403


async def test_institution_head_can_submit(client: AsyncClient, as_institution_head, seed_refs) -> None:
    await seed_refs()
    as_institution_head()
    response = await client.post("/api/v1/course-requests", json=REQUEST_PAYLOAD)
    assert response.status_code == 201
