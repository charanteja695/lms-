"""Turns domain events into notifications. Payload contracts (all ids are public ids as strings):

  enrollment.created          {enrollment_id, batch_id, student_user_id, organization_id, version_id}
  enrollment.removed          {enrollment_id, batch_id, student_user_id, version_id}
  course.eligible_for_final   {enrollment_id, version_id, student_user_id}
  course_request.decided      {course_request_id, decision, reason?, organization_id, course_id, requested_by}
                              only "rejected" notifies: an approval reaches the institution heads
                              through subscription.activated instead
  subscription.activated      {subscription_id, organization_id, course_id, seats_total, ends_at}
  subscription.cancelled      {subscription_id, organization_id, course_id, reason}
  subscription.expired        {subscription_id, organization_id, course_id}

An event missing a field it needs (published before its producer was extended) is skipped, not failed:
a poison message would otherwise block the consumer.
"""

import logging
from typing import Any

from lms_common.events import Event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.services.course_ref_service import CourseRefService
from app.services.notification_service import NotificationService, Recipient
from app.services.recipient_service import RecipientService

logger = logging.getLogger(__name__)


def _id(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    return int(value) if value not in (None, "") else None


def _ids(payload: dict[str, Any], *keys: str) -> dict[str, str]:
    return {key: str(payload[key]) for key in keys if payload.get(key) not in (None, "")}


async def _send(
    db: AsyncSession,
    settings: Settings,
    event: Event,
    type_key: str,
    recipients: list[Recipient],
    context: dict[str, str],
    data: dict[str, str],
) -> None:
    await NotificationService(db, settings).notify(
        event_id=event.event_id, type_key=type_key, recipients=recipients, context=context, data=data
    )


async def _to_student(db: AsyncSession, settings: Settings, event: Event, type_key: str) -> None:
    student_id, version_id = _id(event.payload, "student_user_id"), _id(event.payload, "version_id")
    if student_id is None or version_id is None:
        logger.warning("Event lacks recipient fields; skipped", extra={"extra_fields": {"event": event.event_type}})
        return
    title = await CourseRefService(db).title_for_version(version_id)
    await _send(
        db,
        settings,
        event,
        type_key,
        await RecipientService(db).for_user(student_id),
        {"course_title": title},
        _ids(event.payload, "enrollment_id", "batch_id"),
    )


async def handle_enrollment_created(db: AsyncSession, event: Event, settings: Settings) -> None:
    await _to_student(db, settings, event, "enrollment.created")


async def handle_enrollment_removed(db: AsyncSession, event: Event, settings: Settings) -> None:
    await _to_student(db, settings, event, "enrollment.removed")


async def handle_eligible_for_final(db: AsyncSession, event: Event, settings: Settings) -> None:
    await _to_student(db, settings, event, "course.eligible_for_final")


async def handle_course_request_decided(db: AsyncSession, event: Event, settings: Settings) -> None:
    if event.payload.get("decision") != "rejected":
        return
    requester_id, course_id = _id(event.payload, "requested_by"), _id(event.payload, "course_id")
    if requester_id is None or course_id is None:
        logger.warning("Event lacks recipient fields; skipped", extra={"extra_fields": {"event": event.event_type}})
        return
    title = await CourseRefService(db).title_for_course(course_id)
    await _send(
        db,
        settings,
        event,
        "course_request.rejected",
        await RecipientService(db).for_user(requester_id),
        {"course_title": title, "reason": str(event.payload.get("reason") or "No reason given")},
        _ids(event.payload, "course_request_id", "course_id"),
    )


async def _to_institution_heads(
    db: AsyncSession, settings: Settings, event: Event, type_key: str, extra_context: dict[str, str]
) -> None:
    organization_id, course_id = _id(event.payload, "organization_id"), _id(event.payload, "course_id")
    if organization_id is None or course_id is None:
        logger.warning("Event lacks recipient fields; skipped", extra={"extra_fields": {"event": event.event_type}})
        return
    title = await CourseRefService(db).title_for_course(course_id)
    await _send(
        db,
        settings,
        event,
        type_key,
        await RecipientService(db).institution_heads(organization_id),
        {"course_title": title, **extra_context},
        _ids(event.payload, "subscription_id", "course_id"),
    )


async def handle_subscription_activated(db: AsyncSession, event: Event, settings: Settings) -> None:
    await _to_institution_heads(
        db,
        settings,
        event,
        "subscription.activated",
        {"seats": str(event.payload.get("seats_total", "")), "ends_on": str(event.payload.get("ends_at", ""))[:10]},
    )


async def handle_subscription_cancelled(db: AsyncSession, event: Event, settings: Settings) -> None:
    await _to_institution_heads(
        db, settings, event, "subscription.cancelled", {"reason": str(event.payload.get("reason") or "No reason given")}
    )


async def handle_subscription_expired(db: AsyncSession, event: Event, settings: Settings) -> None:
    await _to_institution_heads(db, settings, event, "subscription.expired", {})
