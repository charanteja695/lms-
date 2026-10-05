from httpx import AsyncClient
from sqlalchemy import select

from app.models.delivery import Delivery
from app.models.notification import Notification
from tests.conftest import STUDENT_ID, SUPER_ADMIN_ID, TEST_ORG_ID, TEST_VERSION_ID, course_payload, user_payload

URL = "/api/v1/notification-templates/enrollment.created/email"


async def test_only_a_super_admin_may_touch_templates(client: AsyncClient, authed) -> None:
    for role in ("student", "institution_head", "admin"):
        authed(user_id=STUDENT_ID, role=role, organization_id=TEST_ORG_ID)
        assert (await client.get("/api/v1/notification-templates")).status_code == 403, role
        assert (await client.put(URL, json={"subject": "s", "body": "b"})).status_code == 403, role
        assert (await client.delete(URL)).status_code == 403, role


async def test_super_admin_lists_every_type_and_channel_with_its_allowed_placeholders(client: AsyncClient, authed) -> None:
    authed(user_id=SUPER_ADMIN_ID, role="super_admin")
    templates = (await client.get("/api/v1/notification-templates")).json()["templates"]
    assert len(templates) == 14  # 7 notification types x 2 channels
    enrollment = next(t for t in templates if t["type"] == "enrollment.created" and t["channel"] == "email")
    assert enrollment["is_customised"] is False and enrollment["subject"] == enrollment["default_subject"]
    assert enrollment["variables"] == ["app_url", "course_title", "first_name"]


async def test_an_override_changes_the_next_notification_and_reset_restores_the_default(
    client: AsyncClient, authed, publish, sessionmaker
) -> None:
    authed(user_id=SUPER_ADMIN_ID, role="super_admin")
    saved = await client.put(URL, json={"subject": "Welcome to ${course_title}!", "body": "Hi ${first_name},\nEnjoy ${course_title}."})
    assert saved.status_code == 200
    assert saved.json()["template"]["is_customised"] is True

    await publish("user.created", user_payload(STUDENT_ID))
    await publish("course.published", course_payload())
    enrolled = {"enrollment_id": "1", "batch_id": "2", "student_user_id": str(STUDENT_ID),
                "organization_id": str(TEST_ORG_ID), "version_id": str(TEST_VERSION_ID)}
    await publish("enrollment.created", enrolled)
    async with sessionmaker() as db:
        delivery = (await db.execute(select(Delivery))).scalar_one()
        notification = (await db.execute(select(Notification))).scalar_one()
    assert delivery.subject == "Welcome to Python Basics!"
    assert delivery.body == "Hi Asha,\nEnjoy Python Basics."  # the line break survives
    assert notification.title == "You are enrolled in Python Basics"  # the in-app template was not overridden

    reset = await client.delete(URL)
    assert reset.json()["template"]["is_customised"] is False
    await publish("enrollment.created", enrolled)
    async with sessionmaker() as db:
        subjects = sorted(d.subject for d in (await db.execute(select(Delivery))).scalars())
    assert subjects == ["Welcome to Python Basics!", "You are enrolled in Python Basics"]


async def test_bad_placeholders_and_unknown_types_are_rejected(client: AsyncClient, authed) -> None:
    authed(user_id=SUPER_ADMIN_ID, role="super_admin")
    bad = await client.put(URL, json={"subject": "Hi ${who}", "body": "ok"})
    assert bad.status_code == 422
    assert bad.json()["details"][0] == {
        "field": "subject",
        "code": "UNKNOWN_PLACEHOLDER",
        "message": "Unknown placeholder(s): who. Allowed: app_url, course_title, first_name",
    }
    assert (await client.put("/api/v1/notification-templates/no.such.type/email", json={"subject": "s", "body": "b"})).status_code == 404
    assert (await client.put("/api/v1/notification-templates/enrollment.created/sms", json={"subject": "s", "body": "b"})).status_code == 422
    assert (await client.put(URL, json={"subject": "", "body": "b"})).status_code == 422
