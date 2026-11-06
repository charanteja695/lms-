from httpx import AsyncClient

from app.permissions.scopes import Scope

AUTHOR = (Scope.CONTENT_AUTHOR.value,)


async def _create_course(client: AsyncClient, authed, slug: str) -> str:
    authed(scopes=AUTHOR)
    response = await client.post(
        "/api/v1/courses", json={"title": "A Course", "slug": slug, "summary": "Ten characters or more of summary."}
    )
    return response.json()["course"]["course_id"]


async def test_publish_requires_at_least_one_course(client: AsyncClient, authed) -> None:
    authed(scopes=AUTHOR)
    path = (
        await client.post(
            "/api/v1/learning-paths",
            json={"title": "Full-Stack Track", "slug": "full-stack-track", "description": "A complete beginner to job-ready track."},
        )
    ).json()["learning_path"]

    response = await client.post(f"/api/v1/learning-paths/{path['learning_path_id']}/publish")
    assert response.status_code == 400
    assert response.json()["code"] == "EMPTY_LEARNING_PATH"


async def test_add_reorder_and_publish_learning_path(client: AsyncClient, authed) -> None:
    course_a = await _create_course(client, authed, "course-a")
    course_b = await _create_course(client, authed, "course-b")

    authed(scopes=AUTHOR)
    path = (
        await client.post(
            "/api/v1/learning-paths",
            json={"title": "Full-Stack Track", "slug": "full-stack-track-2", "description": "A complete beginner to job-ready track."},
        )
    ).json()["learning_path"]
    path_id = path["learning_path_id"]

    await client.post(f"/api/v1/learning-paths/{path_id}/courses", json={"course_id": course_a})
    await client.post(f"/api/v1/learning-paths/{path_id}/courses", json={"course_id": course_b})

    response = await client.put(f"/api/v1/learning-paths/{path_id}/courses/reorder", json={"ordered_ids": [course_b, course_a]})
    assert response.status_code == 200
    assert [item["course_id"] for item in response.json()["learning_path"]["items"]] == [course_b, course_a]

    response = await client.post(f"/api/v1/learning-paths/{path_id}/publish")
    assert response.status_code == 200
    assert response.json()["learning_path"]["status"] == "published"

    response = await client.post(f"/api/v1/learning-paths/{path_id}/courses", json={"course_id": course_a})
    assert response.status_code == 409
    assert response.json()["code"] == "LEARNING_PATH_NOT_DRAFT"

    response = await client.post(f"/api/v1/learning-paths/{path_id}/archive")
    assert response.status_code == 200
    assert response.json()["learning_path"]["status"] == "archived"


async def test_adding_the_same_course_twice_is_a_conflict(client: AsyncClient, authed) -> None:
    course_a = await _create_course(client, authed, "course-dup")
    authed(scopes=AUTHOR)
    path = (
        await client.post(
            "/api/v1/learning-paths",
            json={"title": "Track", "slug": "track-dup", "description": "A complete beginner to job-ready track."},
        )
    ).json()["learning_path"]

    await client.post(f"/api/v1/learning-paths/{path['learning_path_id']}/courses", json={"course_id": course_a})
    response = await client.post(f"/api/v1/learning-paths/{path['learning_path_id']}/courses", json={"course_id": course_a})
    assert response.status_code == 409


async def test_draft_learning_paths_are_hidden_from_readers(client: AsyncClient, authed) -> None:
    authed(scopes=AUTHOR)
    draft = (await client.post("/api/v1/learning-paths", json={"title": "Data Analyst Path", "slug": "data-analyst", "description": "From spreadsheets to dashboards, step by step."})).json()["learning_path"]
    authed(role="student", scopes=("catalog.read",))
    assert draft["learning_path_id"] not in {p["learning_path_id"] for p in (await client.get("/api/v1/learning-paths")).json()["learning_paths"]}
    assert (await client.get(f"/api/v1/learning-paths/{draft['learning_path_id']}")).status_code == 404
    authed(scopes=AUTHOR)
    assert (await client.get(f"/api/v1/learning-paths/{draft['learning_path_id']}")).status_code == 200
