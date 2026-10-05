from httpx import AsyncClient
from sqlalchemy import select

from app.models.delivery import Delivery
from app.models.notification import Notification
from tests.conftest import (
    HEAD_ID,
    STUDENT_ID,
    TEST_COURSE_ID,
    TEST_ORG_ID,
    TEST_VERSION_ID,
    course_payload,
    user_payload,
)


async def test_defaults_show_email_on_and_which_categories_are_locked(client: AsyncClient, authed) -> None:
    authed(user_id=STUDENT_ID)
    response = await client.get("/api/v1/notification-preferences")
    assert response.status_code == 200
    by_category = {p["category"]: p for p in response.json()["preferences"]}
    assert by_category["enrollment"] == {"category": "enrollment", "label": "Enrolments", "email_enabled": True, "email_editable": True}
    assert by_category["subscription"]["email_editable"] is False


async def test_switching_a_category_off_is_saved_and_returned(client: AsyncClient, authed) -> None:
    authed(user_id=STUDENT_ID)
    response = await client.put("/api/v1/notification-preferences", json={"preferences": [{"category": "learning", "email_enabled": False}]})
    assert response.status_code == 200
    assert {p["category"]: p["email_enabled"] for p in response.json()["preferences"]}["learning"] is False

    again = await client.put("/api/v1/notification-preferences", json={"preferences": [{"category": "learning", "email_enabled": True}]})
    assert {p["category"]: p["email_enabled"] for p in again.json()["preferences"]}["learning"] is True


async def test_preferences_are_per_user(client: AsyncClient, authed) -> None:
    authed(user_id=STUDENT_ID)
    await client.put("/api/v1/notification-preferences", json={"preferences": [{"category": "enrollment", "email_enabled": False}]})
    authed(user_id=HEAD_ID)
    prefs = {p["category"]: p["email_enabled"] for p in (await client.get("/api/v1/notification-preferences")).json()["preferences"]}
    assert prefs["enrollment"] is True


async def test_locked_and_unknown_categories_are_rejected(client: AsyncClient, authed) -> None:
    authed(user_id=STUDENT_ID)
    locked = await client.put("/api/v1/notification-preferences", json={"preferences": [{"category": "subscription", "email_enabled": False}]})
    assert locked.status_code == 422
    assert locked.json()["details"][0]["code"] == "PREFERENCE_LOCKED"
    unknown = await client.put("/api/v1/notification-preferences", json={"preferences": [{"category": "marketing", "email_enabled": False}]})
    assert unknown.status_code == 422
    assert (await client.put("/api/v1/notification-preferences", json={"preferences": []})).status_code == 422
    assert (await client.put("/api/v1/notification-preferences", json={"preferences": [{"category": "learning", "email_enabled": False, "x": 1}]})).status_code == 422


async def test_an_email_opt_out_keeps_the_inbox_row_but_sends_no_email(client: AsyncClient, authed, publish, sessionmaker) -> None:
    await publish("user.created", user_payload(STUDENT_ID))
    await publish("course.published", course_payload())
    authed(user_id=STUDENT_ID)
    await client.put("/api/v1/notification-preferences", json={"preferences": [{"category": "enrollment", "email_enabled": False}]})

    await publish(
        "enrollment.created",
        {"enrollment_id": "1", "batch_id": "2", "student_user_id": str(STUDENT_ID),
         "organization_id": str(TEST_ORG_ID), "version_id": str(TEST_VERSION_ID)},
    )
    async with sessionmaker() as db:
        assert len(list((await db.execute(select(Notification))).scalars())) == 1
        assert list((await db.execute(select(Delivery))).scalars()) == []


async def test_a_locked_category_is_emailed_regardless(publish, sessionmaker) -> None:
    await publish("user.created", user_payload(HEAD_ID, role="institution_head"))
    await publish("subscription.expired", {"subscription_id": "1", "organization_id": str(TEST_ORG_ID), "course_id": str(TEST_COURSE_ID)})
    async with sessionmaker() as db:
        assert len(list((await db.execute(select(Delivery))).scalars())) == 1
