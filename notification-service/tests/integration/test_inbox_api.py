from httpx import AsyncClient

from tests.conftest import HEAD_ID, STUDENT_ID, TEST_ORG_ID, TEST_VERSION_ID, course_payload, user_payload


async def _enrol(publish, student_id: int, enrollment_id: str) -> None:
    await publish(
        "enrollment.created",
        {"enrollment_id": enrollment_id, "batch_id": "1755000000006302", "student_user_id": str(student_id),
         "organization_id": str(TEST_ORG_ID), "version_id": str(TEST_VERSION_ID)},
    )


async def _seed(publish) -> None:
    await publish("user.created", user_payload(STUDENT_ID))
    await publish("user.created", user_payload(HEAD_ID, role="institution_head"))
    await publish("course.published", course_payload())


async def test_missing_token_is_rejected(client: AsyncClient) -> None:
    for method, path in (("GET", "/notifications"), ("GET", "/notifications/unread-count"), ("POST", "/notifications/read-all"),
                         ("GET", "/notification-preferences")):
        response = await client.request(method, f"/api/v1{path}")
        assert response.status_code == 401, path
        assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_inbox_lists_only_my_notifications_newest_first(client: AsyncClient, authed, publish) -> None:
    await _seed(publish)
    await _enrol(publish, STUDENT_ID, "1755000000006701")
    await _enrol(publish, STUDENT_ID, "1755000000006702")
    await _enrol(publish, HEAD_ID, "1755000000006703")  # someone else's

    authed(user_id=STUDENT_ID)
    response = await client.get("/api/v1/notifications")
    assert response.status_code == 200
    body = response.json()
    assert [n["data"]["enrollment_id"] for n in body["notifications"]] == ["1755000000006702", "1755000000006701"]
    assert body["page_context"]["total_records"] == 2
    first = body["notifications"][0]
    assert isinstance(first["notification_id"], str)
    assert first["type"] == "enrollment.created" and first["read_at"] is None


async def test_unread_count_mark_read_and_filter(client: AsyncClient, authed, publish) -> None:
    await _seed(publish)
    await _enrol(publish, STUDENT_ID, "1755000000006701")
    await _enrol(publish, STUDENT_ID, "1755000000006702")
    authed(user_id=STUDENT_ID)

    assert (await client.get("/api/v1/notifications/unread-count")).json()["unread_count"] == 2
    notification_id = (await client.get("/api/v1/notifications")).json()["notifications"][0]["notification_id"]

    read = await client.post(f"/api/v1/notifications/{notification_id}/read")
    assert read.status_code == 200 and read.json()["notification"]["read_at"] is not None
    first_read_at = read.json()["notification"]["read_at"]
    again = await client.post(f"/api/v1/notifications/{notification_id}/read")  # idempotent
    assert again.json()["notification"]["read_at"] == first_read_at

    assert (await client.get("/api/v1/notifications/unread-count")).json()["unread_count"] == 1
    unread = (await client.get("/api/v1/notifications", params={"unread": "true"})).json()
    assert len(unread["notifications"]) == 1 and unread["notifications"][0]["notification_id"] != notification_id


async def test_read_all_marks_everything_mine_and_nothing_else(client: AsyncClient, authed, publish) -> None:
    await _seed(publish)
    await _enrol(publish, STUDENT_ID, "1755000000006701")
    await _enrol(publish, HEAD_ID, "1755000000006703")

    authed(user_id=STUDENT_ID)
    response = await client.post("/api/v1/notifications/read-all")
    assert response.json()["updated_count"] == 1
    assert (await client.get("/api/v1/notifications/unread-count")).json()["unread_count"] == 0

    authed(user_id=HEAD_ID)
    assert (await client.get("/api/v1/notifications/unread-count")).json()["unread_count"] == 1


async def test_another_users_notification_looks_like_it_does_not_exist(client: AsyncClient, authed, publish) -> None:
    await _seed(publish)
    await _enrol(publish, STUDENT_ID, "1755000000006701")
    authed(user_id=STUDENT_ID)
    notification_id = (await client.get("/api/v1/notifications")).json()["notifications"][0]["notification_id"]

    authed(user_id=HEAD_ID)
    response = await client.post(f"/api/v1/notifications/{notification_id}/read")
    assert response.status_code == 404
    assert response.json()["code"] == "NOTIFICATION_NOT_FOUND"
    assert (await client.post("/api/v1/notifications/not-an-id/read")).status_code == 404


async def test_pagination_reports_more_pages(client: AsyncClient, authed, publish) -> None:
    await _seed(publish)
    for number in range(3):
        await _enrol(publish, STUDENT_ID, f"175500000000670{number}")
    authed(user_id=STUDENT_ID)
    page = (await client.get("/api/v1/notifications", params={"per_page": 2})).json()
    assert len(page["notifications"]) == 2
    assert page["page_context"]["has_more_page"] is True and page["page_context"]["total_pages"] == 2
    assert (await client.get("/api/v1/notifications", params={"per_page": 500})).status_code == 422
