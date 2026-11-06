from httpx import AsyncClient

from app.permissions.scopes import Scope

COURSE_PAYLOAD = {"title": "Full Stack Development with MERN", "slug": "mern-full-stack", "summary": "Build production web apps end to end."}


async def test_missing_token_is_rejected_without_any_network_call(client: AsyncClient) -> None:
    response = await client.post("/api/v1/courses", json=COURSE_PAYLOAD)
    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_token_without_content_author_scope_is_forbidden(client: AsyncClient, authed) -> None:
    authed(scopes=())
    response = await client.post("/api/v1/courses", json=COURSE_PAYLOAD)
    assert response.status_code == 403


async def test_token_with_content_author_scope_is_allowed(client: AsyncClient, authed) -> None:
    authed(scopes=(Scope.CONTENT_AUTHOR.value,))
    response = await client.post("/api/v1/courses", json=COURSE_PAYLOAD)
    assert response.status_code == 201


async def test_reviewer_scope_cannot_author(client: AsyncClient, authed) -> None:
    authed(scopes=(Scope.CONTENT_REVIEW.value,))
    response = await client.post("/api/v1/courses", json=COURSE_PAYLOAD)
    assert response.status_code == 403
