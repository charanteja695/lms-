"""Inbound event handlers (payload contracts of the producers).

  user.created/updated/suspended/activated/deleted   user-management: {user_id, email, first_name, last_name, role, status, organization_id}
  course.published                                   catalog-service: {course_id, title, ...}
  certificate.issued                                 certificate-service: {certificate_id, student_user_id, organization_id, course_id, grade,
                                                     score_percent, completion_date, issued_at, verification_url}
  certificate.revoked                                certificate-service: {certificate_id, student_user_id, course_id, reason}
  attempt.finalized                                  assessment-service: {attempt_id, user_id, course_id, test_kind, result, percent, revision, ...}

``attempt.graded`` is deliberately not consumed: a graded attempt may still be waiting for an integrity decision, and a skill
score printed on a resume must only come from a released result.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.refs import CourseRef, UserRef
from app.services.verified_service import VerifiedService, _int


async def handle_user_upserted(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    user_id = _int(payload.get("user_id"))
    if user_id is None:
        return
    ref = await db.get(UserRef, user_id)
    if ref is None:
        ref = UserRef(user_id=user_id)
        db.add(ref)
    ref.first_name = str(payload.get("first_name") or "")[:100]
    ref.last_name = str(payload.get("last_name") or "")[:100]
    ref.email = str(payload["email"])[:320] if payload.get("email") else ref.email
    ref.role = str(payload.get("role") or "")[:20]
    ref.organization_id = _int(payload.get("organization_id"))
    ref.active = payload.get("status", "active") == "active"


async def handle_user_deleted(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    user_id = _int(payload.get("user_id"))
    ref = await db.get(UserRef, user_id) if user_id is not None else None
    if ref is not None:
        ref.active = False


async def handle_course_published(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    course_id = _int(payload.get("course_id"))
    if course_id is None:
        return
    ref = await db.get(CourseRef, course_id)
    if ref is None:
        ref = CourseRef(course_id=course_id, title="")
        db.add(ref)
    ref.title = str(payload.get("title") or ref.title)[:300]


async def handle_certificate_issued(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    await VerifiedService(db, settings).certificate_issued(payload)


async def handle_certificate_revoked(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    await VerifiedService(db, settings).certificate_revoked(payload)


async def handle_attempt_finalized(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    await VerifiedService(db, settings).attempt_finalized(payload)
