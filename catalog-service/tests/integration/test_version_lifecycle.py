from httpx import AsyncClient

from app.api.deps import _authenticate
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


async def _add_full_module(
    client: AsyncClient, authed, course_id: str, version_id: str, *, topic_test_id: str | None = "1755000000000333"
) -> None:
    authed(scopes=AUTHOR)
    base = f"/api/v1/courses/{course_id}/versions/{version_id}"
    module = (await client.post(f"{base}/modules", json={"title": "JavaScript Fundamentals"})).json()["module"]
    topics = f"{base}/modules/{module['module_id']}/topics"
    topic = (await client.post(topics, json={"title": "Variables & Types"})).json()["topic"]
    if topic_test_id:  # in the product, catalog attaches it when the topic's test is published (test.published)
        await client.patch(f"{topics}/{topic['topic_id']}", json={"topic_test_id": topic_test_id})
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


async def test_submit_fails_while_a_topic_has_no_topic_test(client: AsyncClient, authed) -> None:
    course_id, version_id = await _course_and_version(client, authed)
    await _add_full_module(client, authed, course_id, version_id, topic_test_id=None)
    authed(scopes=AUTHOR)
    response = await client.post(f"/api/v1/courses/{course_id}/versions/{version_id}/submit")
    assert response.status_code == 400
    assert response.json()["code"] == "TOPIC_TEST_MISSING"
    assert "Variables & Types" in response.json()["message"]


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


async def test_content_needs_a_reader_and_drafts_stay_with_their_authors(client: AsyncClient, authed, app) -> None:
    """A signed-out caller sees nothing; a student reads published content only; an employer can list courses but not
    open their content; the review trail is for authors and reviewers."""
    course_id, version_id = await _course_and_version(client, authed)
    await _add_full_module(client, authed, course_id, version_id)
    base = f"/api/v1/courses/{course_id}/versions/{version_id}"

    student = ("catalog.read",)
    authed(role="student", scopes=student)
    assert (await client.get(base)).status_code == 404  # still a draft
    assert (await client.get(f"{base}/reviews")).status_code == 403

    authed(scopes=AUTHOR)
    await client.post(f"{base}/submit")
    authed(scopes=REVIEWER)
    await client.post(f"{base}/approve")

    authed(role="student", scopes=student)
    published = await client.get(base)
    assert published.status_code == 200 and published.json()["version"]["status"] == "published"
    authed(role="student", scopes=())  # a super admin removed "read course content" from this student
    assert (await client.get(base)).status_code == 403

    authed(role="employer_admin", scopes=())
    assert (await client.get("/api/v1/courses")).status_code == 200  # names only, e.g. for job requirements
    assert (await client.get(base)).status_code == 403

    app.dependency_overrides.pop(_authenticate, None)
    assert (await client.get("/api/v1/courses")).status_code == 401
