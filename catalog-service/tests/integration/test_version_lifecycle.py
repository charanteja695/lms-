from httpx import AsyncClient

from app.permissions.scopes import Scope

AUTHOR = (Scope.CONTENT_AUTHOR.value,)
REVIEWER = (Scope.CONTENT_REVIEW.value,)


async def _course_and_version(client: AsyncClient, authed, *, slug: str = "mern-full-stack") -> tuple[str, str]:
    authed(scopes=AUTHOR)
    response = await client.post(
        "/api/v1/courses",
        json={"title": "Full Stack Development with MERN", "slug": slug, "summary": "Build production web apps end to end."},
    )
    course = response.json()["course"]
    return course["course_id"], course["versions"][0]["version_id"]


async def _add_full_module(client: AsyncClient, authed, course_id: str, version_id: str) -> None:
    authed(scopes=AUTHOR)
    base = f"/api/v1/courses/{course_id}/versions/{version_id}"
    module = (await client.post(f"{base}/modules", json={"title": "JavaScript Fundamentals"})).json()["module"]
    topic = (
        await client.post(f"{base}/modules/{module['module_id']}/topics", json={"title": "Variables & Types"})
    ).json()["topic"]
    await client.post(
        f"{base}/modules/{module['module_id']}/topics/{topic['topic_id']}/items",
        json={"item_type": "notes", "title": "Reading: var, let and const", "content_text": "Notes go here."},
    )


async def test_submit_fails_when_course_has_no_modules(client: AsyncClient, authed) -> None:
    course_id, version_id = await _course_and_version(client, authed)
    authed(scopes=AUTHOR)
    response = await client.post(f"/api/v1/courses/{course_id}/versions/{version_id}/submit")
    assert response.status_code == 400
    assert response.json()["code"] == "EMPTY_COURSE"


async def test_full_lifecycle_draft_to_published_to_retired(client: AsyncClient, authed) -> None:
    course_id, version_id = await _course_and_version(client, authed)
    await _add_full_module(client, authed, course_id, version_id)
    base = f"/api/v1/courses/{course_id}/versions/{version_id}"

    authed(scopes=AUTHOR)
    response = await client.post(f"{base}/submit")
    assert response.status_code == 200
    assert response.json()["version"]["status"] == "in_review"

    authed(scopes=REVIEWER)
    response = await client.post(f"{base}/approve")
    assert response.status_code == 200
    assert response.json()["version"]["status"] == "published"
    assert response.json()["version"]["published_at"] is not None

    # A published version is immutable: no more structural edits.
    authed(scopes=AUTHOR)
    response = await client.post(f"{base}/modules", json={"title": "Another module"})
    assert response.status_code == 400
    assert response.json()["code"] == "VERSION_NOT_DRAFT"

    authed(scopes=REVIEWER)
    response = await client.post(f"{base}/retire")
    assert response.status_code == 200
    assert response.json()["version"]["status"] == "archived"


async def test_reject_sends_version_back_to_draft_with_reason(client: AsyncClient, authed) -> None:
    course_id, version_id = await _course_and_version(client, authed)
    await _add_full_module(client, authed, course_id, version_id)
    base = f"/api/v1/courses/{course_id}/versions/{version_id}"

    authed(scopes=AUTHOR)
    await client.post(f"{base}/submit")

    authed(scopes=REVIEWER)
    response = await client.post(f"{base}/reject", json={"reason": "The topic test is missing a pass mark"})
    assert response.status_code == 200
    body = response.json()["version"]
    assert body["status"] == "draft"
    assert body["reject_reason"] == "The topic test is missing a pass mark"

    response = await client.get(f"{base}/reviews")
    assert response.status_code == 200
    actions = [review["action"] for review in response.json()["reviews"]]
    assert actions == ["rejected", "submitted"]


async def test_only_one_non_terminal_version_per_course(client: AsyncClient, authed) -> None:
    course_id, _version_id = await _course_and_version(client, authed)
    authed(scopes=AUTHOR)
    response = await client.post(f"/api/v1/courses/{course_id}/versions")
    assert response.status_code == 409
    assert response.json()["code"] == "DRAFT_ALREADY_EXISTS"


async def test_reorder_modules(client: AsyncClient, authed) -> None:
    course_id, version_id = await _course_and_version(client, authed)
    base = f"/api/v1/courses/{course_id}/versions/{version_id}"
    authed(scopes=AUTHOR)
    first = (await client.post(f"{base}/modules", json={"title": "Module A"})).json()["module"]
    second = (await client.post(f"{base}/modules", json={"title": "Module B"})).json()["module"]

    response = await client.put(f"{base}/modules/reorder", json={"ordered_ids": [second["module_id"], first["module_id"]]})
    assert response.status_code == 204

    detail = (await client.get(base)).json()["version"]
    titles = [module["title"] for module in detail["modules"]]
    assert titles == ["Module B", "Module A"]
