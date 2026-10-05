from httpx import AsyncClient

from app.permissions.scopes import Scope

AUTHOR = (Scope.CONTENT_AUTHOR.value,)


async def _create_course(client: AsyncClient, authed, *, slug: str = "mern-full-stack") -> dict:
    authed(scopes=AUTHOR)
    response = await client.post(
        "/api/v1/courses",
        json={"title": "Full Stack Development with MERN", "slug": slug, "summary": "Build production web apps end to end."},
    )
    assert response.status_code == 201, response.text
    return response.json()["course"]


async def test_create_course_also_creates_its_first_draft_version(client: AsyncClient, authed) -> None:
    course = await _create_course(client, authed)
    assert course["slug"] == "mern-full-stack"
    assert len(course["versions"]) == 1
    assert course["versions"][0]["version_number"] == 1
    assert course["versions"][0]["status"] == "draft"


async def test_duplicate_slug_is_a_conflict(client: AsyncClient, authed) -> None:
    await _create_course(client, authed, slug="duplicate-slug")
    authed(scopes=AUTHOR)
    response = await client.post(
        "/api/v1/courses",
        json={"title": "Another Course", "slug": "duplicate-slug", "summary": "Something else entirely, ten chars+."},
    )
    assert response.status_code == 409


async def test_get_course_by_public_id(client: AsyncClient, authed) -> None:
    course = await _create_course(client, authed)
    authed(scopes=())
    response = await client.get(f"/api/v1/courses/{course['course_id']}")
    assert response.status_code == 200
    assert response.json()["course"]["course_id"] == course["course_id"]


async def test_get_unknown_course_is_404(client: AsyncClient, authed) -> None:
    authed(scopes=())
    response = await client.get("/api/v1/courses/1755000000000999")
    assert response.status_code == 404
    assert response.json()["code"] == "COURSE_NOT_FOUND"


async def test_update_course_requires_author_scope(client: AsyncClient, authed) -> None:
    course = await _create_course(client, authed)
    authed(scopes=())
    response = await client.patch(f"/api/v1/courses/{course['course_id']}", json={"title": "New Title"})
    assert response.status_code == 403

    authed(scopes=AUTHOR)
    response = await client.patch(f"/api/v1/courses/{course['course_id']}", json={"title": "New Title"})
    assert response.status_code == 200
    assert response.json()["course"]["title"] == "New Title"


async def test_list_courses_paginates(client: AsyncClient, authed) -> None:
    await _create_course(client, authed, slug="course-one")
    await _create_course(client, authed, slug="course-two")
    authed(scopes=())
    response = await client.get("/api/v1/courses", params={"per_page": 1, "page": 1})
    assert response.status_code == 200
    body = response.json()
    assert len(body["courses"]) == 1
    assert body["page_context"]["total_records"] == 2
    assert body["page_context"]["has_more_page"] is True
