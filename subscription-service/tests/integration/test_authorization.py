from httpx import AsyncClient

from tests.conftest import TEST_ORG_ID

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


async def test_course_requests_follow_the_persons_permission(client: AsyncClient, authed) -> None:
    """A super admin can let one staff member request courses, or stop a head."""
    authed(role="staff", organization_id=TEST_ORG_ID)
    assert (await client.post("/api/v1/course-requests", json=REQUEST_PAYLOAD)).status_code == 403
    authed(role="institution_head", organization_id=TEST_ORG_ID, defaults=False)
    assert (await client.post("/api/v1/course-requests", json=REQUEST_PAYLOAD)).status_code == 403
    authed(role="staff", organization_id=TEST_ORG_ID, scopes=("subscriptions.request",))
    assert (await client.post("/api/v1/course-requests", json=REQUEST_PAYLOAD)).status_code != 403


async def test_an_admin_reaches_only_the_institutions_they_look_after(client: AsyncClient, app, as_institution_head, seed_refs) -> None:
    from dataclasses import replace

    from app.api.deps import _authenticate
    from tests.conftest import make_claims

    await seed_refs()
    as_institution_head()
    request_id = (await client.post("/api/v1/course-requests", json=REQUEST_PAYLOAD)).json()["course_request"]["course_request_id"]

    other_admin = replace(make_claims(role="admin", scopes=("accounts.manage",)), admin_organization_ids=(1755000000009999,))
    app.dependency_overrides[_authenticate] = lambda: other_admin
    assert (await client.get("/api/v1/course-requests")).json()["course_requests"] == []
    assert (await client.get(f"/api/v1/course-requests/{request_id}")).status_code == 403
    assert (await client.post(f"/api/v1/course-requests/{request_id}/approve", json={})).status_code == 403

    own_admin = replace(other_admin, admin_organization_ids=(TEST_ORG_ID,))
    app.dependency_overrides[_authenticate] = lambda: own_admin
    assert [r["course_request_id"] for r in (await client.get("/api/v1/course-requests")).json()["course_requests"]] == [request_id]
