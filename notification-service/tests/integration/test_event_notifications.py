from sqlalchemy import func, select

from app.models.delivery import Delivery
from app.models.notification import Notification
from app.models.user_ref import UserRef
from tests.conftest import (
    HEAD_ID,
    OTHER_HEAD_ID,
    STUDENT_ID,
    TEST_COURSE_ID,
    TEST_ORG_ID,
    TEST_VERSION_ID,
    course_payload,
    user_payload,
)

OTHER_ORG_ID = TEST_ORG_ID + 1


async def _all(sessionmaker, model):
    async with sessionmaker() as db:
        return list((await db.execute(select(model))).scalars())


async def _seed_directory(publish) -> None:
    await publish("user.created", user_payload(STUDENT_ID))
    await publish("user.created", user_payload(HEAD_ID, role="institution_head", first_name="Hari"))
    await publish("user.created", user_payload(OTHER_HEAD_ID, role="institution_head", organization_id=OTHER_ORG_ID))
    await publish("course.published", course_payload())


def _enrollment_created(student_id: int = STUDENT_ID) -> dict:
    return {
        "enrollment_id": "1755000000006301",
        "batch_id": "1755000000006302",
        "student_user_id": str(student_id),
        "organization_id": str(TEST_ORG_ID),
        "version_id": str(TEST_VERSION_ID),
    }


async def test_enrollment_creates_an_inbox_row_and_an_email_with_the_course_title(publish, sessionmaker) -> None:
    await _seed_directory(publish)
    await publish("enrollment.created", _enrollment_created())

    [notification] = await _all(sessionmaker, Notification)
    assert notification.recipient_user_id == STUDENT_ID
    assert notification.title == "You are enrolled in Python Basics"
    assert "Hello Asha" in notification.body
    assert notification.data == {"enrollment_id": "1755000000006301", "batch_id": "1755000000006302"}
    [delivery] = await _all(sessionmaker, Delivery)
    assert delivery.to_address == "x@example.com"
    assert delivery.notification_id == notification.id
    assert delivery.status == "pending"


async def test_a_redelivered_event_does_not_notify_twice(publish, sessionmaker) -> None:
    await _seed_directory(publish)
    await publish("enrollment.created", _enrollment_created(), event_id="same-event")
    await publish("enrollment.created", _enrollment_created(), event_id="same-event")

    assert len(await _all(sessionmaker, Notification)) == 1
    assert len(await _all(sessionmaker, Delivery)) == 1


async def test_student_without_an_email_address_gets_in_app_only(publish, sessionmaker) -> None:
    await publish("user.created", user_payload(STUDENT_ID, email=None))
    await publish("enrollment.created", _enrollment_created())

    assert len(await _all(sessionmaker, Notification)) == 1
    assert await _all(sessionmaker, Delivery) == []


async def test_user_unknown_to_the_directory_still_gets_the_in_app_notification(publish, sessionmaker) -> None:
    await publish("enrollment.created", _enrollment_created())

    [notification] = await _all(sessionmaker, Notification)
    assert notification.title == "You are enrolled in your course"  # course.published was never seen either
    assert await _all(sessionmaker, Delivery) == []


async def test_suspended_and_deleted_users_are_not_notified(publish, sessionmaker) -> None:
    await publish("user.created", user_payload(STUDENT_ID))
    await publish("user.suspended", user_payload(STUDENT_ID, status="suspended"))
    await publish("enrollment.created", _enrollment_created())
    assert await _all(sessionmaker, Notification) == []

    await publish("user.activated", user_payload(STUDENT_ID))
    await publish("user.deleted", user_payload(STUDENT_ID, status="deleted"))
    await publish("enrollment.created", _enrollment_created())
    assert await _all(sessionmaker, Notification) == []
    async with sessionmaker() as db:
        assert (await db.get(UserRef, STUDENT_ID)).status == "deleted"


async def test_subscription_activated_reaches_only_that_institutions_heads(publish, sessionmaker) -> None:
    await _seed_directory(publish)
    await publish(
        "subscription.activated",
        {
            "subscription_id": "1755000000006401",
            "organization_id": str(TEST_ORG_ID),
            "course_id": str(TEST_COURSE_ID),
            "seats_total": 50,
            "ends_at": "2027-09-20T10:00:00+00:00",
        },
    )

    [notification] = await _all(sessionmaker, Notification)
    assert notification.recipient_user_id == HEAD_ID  # not the student, not the other institution's head
    assert "50 seats until 2027-09-20" in notification.body
    assert notification.title == "Python Basics is now active for your institution"


async def test_course_request_approval_is_left_to_subscription_activated(publish, sessionmaker) -> None:
    await _seed_directory(publish)
    await publish(
        "course_request.decided",
        {"course_request_id": "1", "decision": "approved", "organization_id": str(TEST_ORG_ID),
         "course_id": str(TEST_COURSE_ID), "requested_by": str(HEAD_ID)},
    )
    assert await _all(sessionmaker, Notification) == []


async def test_course_request_rejection_tells_the_requester_the_reason(publish, sessionmaker) -> None:
    await _seed_directory(publish)
    await publish(
        "course_request.decided",
        {"course_request_id": "1755000000006501", "decision": "rejected", "reason": "Out of budget",
         "organization_id": str(TEST_ORG_ID), "course_id": str(TEST_COURSE_ID), "requested_by": str(HEAD_ID)},
    )

    [notification] = await _all(sessionmaker, Notification)
    assert notification.recipient_user_id == HEAD_ID
    assert "Reason: Out of budget" in notification.body


async def test_cancelled_and_expired_subscriptions_notify_the_heads(publish, sessionmaker) -> None:
    await _seed_directory(publish)
    base = {"subscription_id": "1755000000006401", "organization_id": str(TEST_ORG_ID), "course_id": str(TEST_COURSE_ID)}
    await publish("subscription.cancelled", {**base, "reason": "Non-payment"})
    await publish("subscription.expired", base)

    titles = sorted(n.title for n in await _all(sessionmaker, Notification))
    assert titles == [
        "Your subscription to Python Basics has expired",
        "Your subscription to Python Basics was cancelled",
    ]


async def test_final_test_unlock_and_withdrawal_notify_the_student(publish, sessionmaker) -> None:
    await _seed_directory(publish)
    await publish("course.eligible_for_final", {"enrollment_id": "1", "version_id": str(TEST_VERSION_ID), "student_user_id": str(STUDENT_ID)})
    await publish("enrollment.removed", {"enrollment_id": "1", "batch_id": "2", "student_user_id": str(STUDENT_ID), "version_id": str(TEST_VERSION_ID)})

    notifications = await _all(sessionmaker, Notification)
    assert sorted(n.type_key for n in notifications) == ["course.eligible_for_final", "enrollment.removed"]
    assert {n.recipient_user_id for n in notifications} == {STUDENT_ID}


async def test_an_event_from_before_the_producer_carried_recipients_is_skipped_not_failed(publish, sessionmaker) -> None:
    await _seed_directory(publish)
    await publish("enrollment.removed", {"enrollment_id": "1", "batch_id": "2"})  # no student_user_id
    await publish("subscription.expired", {"subscription_id": "1"})  # no organization_id
    assert await _all(sessionmaker, Notification) == []


async def test_events_this_service_does_not_handle_are_ignored(publish, sessionmaker) -> None:
    await publish("media.ready", {"media_asset_id": "1"})
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count()).select_from(Notification))).scalar_one() == 0
