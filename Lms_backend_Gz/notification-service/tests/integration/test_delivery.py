from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.core.time import utcnow
from app.models.delivery import Delivery
from app.models.outbox_event import OutboxEvent
from app.services.delivery_service import deliver_due
from tests.conftest import STUDENT_ID, SUPER_ADMIN_ID, TEST_ORG_ID, TEST_VERSION_ID, course_payload, user_payload


@pytest.fixture
async def pending_email(publish) -> None:
    await publish("user.created", user_payload(STUDENT_ID))
    await publish("course.published", course_payload())
    await publish(
        "enrollment.created",
        {"enrollment_id": "1", "batch_id": "2", "student_user_id": str(STUDENT_ID),
         "organization_id": str(TEST_ORG_ID), "version_id": str(TEST_VERSION_ID)},
    )


async def _delivery(sessionmaker) -> Delivery:
    async with sessionmaker() as db:
        return (await db.execute(select(Delivery))).scalar_one()


async def _make_due(sessionmaker) -> None:
    async with sessionmaker() as db:
        await db.execute(update(Delivery).values(next_attempt_at=utcnow() - timedelta(seconds=1)))
        await db.commit()


async def _outbox_types(sessionmaker) -> list[str]:
    async with sessionmaker() as db:
        return [e.event_type for e in (await db.execute(select(OutboxEvent).order_by(OutboxEvent.created_at))).scalars()]


async def test_a_pending_email_is_sent_once_and_reported(pending_email, sessionmaker, settings, email_sender) -> None:
    assert await deliver_due(sessionmaker, email_sender, settings) == 1
    assert await deliver_due(sessionmaker, email_sender, settings) == 0  # nothing left to do

    [message] = email_sender.sent
    assert message.to == "x@example.com"
    assert message.subject == "You are enrolled in Python Basics"
    assert "<p>Hello Asha," in message.html_body
    delivery = await _delivery(sessionmaker)
    assert (delivery.status, delivery.attempts, delivery.last_error) == ("sent", 1, None)
    assert delivery.sent_at is not None
    assert await _outbox_types(sessionmaker) == ["notification.delivered"]


async def test_html_alternative_escapes_user_supplied_text(publish, sessionmaker, settings, email_sender) -> None:
    await publish("user.created", user_payload(STUDENT_ID, first_name="<script>x</script>"))
    await publish("course.published", course_payload())
    await publish(
        "enrollment.created",
        {"enrollment_id": "1", "batch_id": "2", "student_user_id": str(STUDENT_ID),
         "organization_id": str(TEST_ORG_ID), "version_id": str(TEST_VERSION_ID)},
    )
    await deliver_due(sessionmaker, email_sender, settings)
    assert "<script>" not in email_sender.sent[0].html_body
    assert "&lt;script&gt;" in email_sender.sent[0].html_body


async def test_a_failure_is_retried_with_backoff_then_given_up_on(pending_email, sessionmaker, settings, email_sender) -> None:
    email_sender.fail_with = ConnectionError("smtp down")

    await deliver_due(sessionmaker, email_sender, settings)
    delivery = await _delivery(sessionmaker)
    assert (delivery.status, delivery.attempts) == ("pending", 1)
    assert "ConnectionError: smtp down" == delivery.last_error
    assert delivery.next_attempt_at > utcnow() + timedelta(seconds=30)  # backing off, not hammering
    assert await deliver_due(sessionmaker, email_sender, settings) == 0  # not due yet

    await _make_due(sessionmaker)
    await deliver_due(sessionmaker, email_sender, settings)
    assert (await _delivery(sessionmaker)).attempts == 2

    await _make_due(sessionmaker)
    await deliver_due(sessionmaker, email_sender, settings)  # third and last attempt (DELIVERY_MAX_ATTEMPTS=3)
    delivery = await _delivery(sessionmaker)
    assert (delivery.status, delivery.attempts) == ("failed", 3)
    assert await _outbox_types(sessionmaker) == ["notification.failed"]
    await _make_due(sessionmaker)
    assert await deliver_due(sessionmaker, email_sender, settings) == 0  # failed deliveries stay put


async def test_a_claimed_delivery_is_not_picked_up_again_while_leased(pending_email, sessionmaker, settings) -> None:
    from app.services.delivery_service import DeliveryService

    async with sessionmaker() as db:
        assert len(await DeliveryService(db, settings).claim_due()) == 1
    async with sessionmaker() as db:
        assert await DeliveryService(db, settings).claim_due() == []


async def test_super_admin_sees_failed_deliveries_and_can_retry_them(
    client: AsyncClient, authed, pending_email, sessionmaker, settings, email_sender
) -> None:
    email_sender.fail_with = ConnectionError("smtp down")
    for _ in range(3):
        await _make_due(sessionmaker)
        await deliver_due(sessionmaker, email_sender, settings)

    authed(user_id=SUPER_ADMIN_ID, role="super_admin")
    failed = (await client.get("/api/v1/deliveries", params={"status": "failed"})).json()
    [item] = failed["deliveries"]
    assert item["status"] == "failed" and item["attempts"] == 3 and item["last_error"] == "ConnectionError: smtp down"
    assert "to_address" not in item  # recipients' addresses are not exposed by the API
    assert (await client.get("/api/v1/deliveries", params={"status": "sent"})).json()["deliveries"] == []

    retried = await client.post(f"/api/v1/deliveries/{item['delivery_id']}/retry")
    assert retried.status_code == 200 and retried.json()["delivery"]["status"] == "pending"
    assert retried.json()["delivery"]["attempts"] == 0

    email_sender.fail_with = None
    await deliver_due(sessionmaker, email_sender, settings)
    assert (await _delivery(sessionmaker)).status == "sent"


async def test_only_failed_deliveries_can_be_retried_and_only_by_a_super_admin(
    client: AsyncClient, authed, pending_email, sessionmaker
) -> None:
    delivery = await _delivery(sessionmaker)

    authed(user_id=STUDENT_ID, role="student", organization_id=TEST_ORG_ID)
    assert (await client.get("/api/v1/deliveries")).status_code == 403
    assert (await client.post(f"/api/v1/deliveries/{delivery.public_id}/retry")).status_code == 403

    authed(user_id=SUPER_ADMIN_ID, role="super_admin")
    pending = await client.post(f"/api/v1/deliveries/{delivery.public_id}/retry")
    assert pending.status_code == 400 and pending.json()["code"] == "DELIVERY_NOT_FAILED"
    assert (await client.post("/api/v1/deliveries/1755000000009999/retry")).status_code == 404
    assert (await client.get("/api/v1/deliveries", params={"status": "bogus"})).status_code == 422
