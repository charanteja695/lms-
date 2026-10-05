"""What this service consumes from ``lms:events`` (payload contracts of the producers):

  course.passed          assessment-service: {"student_user_id", "course_id", "version_id", "enrollment_id", "organization_id",
                         "test_id", "attempt_id", "percent", "passed_at", ...}                    -> issue a certificate
  course.pass_revoked    assessment-service: {"attempt_id", "student_user_id", "course_id", "reason"} -> revoke it
  user.*                 user-management: {"user_id", "first_name", "last_name", "role", "organization_id"}  (students only)
  institution.*          user-management: {"organization_id", "name"}
  course.published       catalog-service: {"course_id", "title", ...}

The directory handlers are idempotent upserts and only supply the words printed on a certificate; the router records each
event id so an issue or a revocation is applied at most once.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.refs import CourseRef, InstitutionRef, UserRef
from app.services.issue_service import IssueService


async def handle_course_passed(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    await IssueService(db, settings).issue_from_pass(payload)


async def handle_pass_revoked(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    await IssueService(db, settings).revoke_from_event(payload)


async def handle_user(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    if payload.get("role") != "student":
        return
    user_id = int(payload["user_id"])
    ref = await db.get(UserRef, user_id)
    if ref is None:
        ref = UserRef(user_id=user_id, first_name="", last_name="")
        db.add(ref)
    ref.first_name, ref.last_name = payload.get("first_name") or "", payload.get("last_name") or ""
    ref.organization_id = int(payload["organization_id"]) if payload.get("organization_id") else None


async def handle_institution(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    organization_id = int(payload["organization_id"])
    ref = await db.get(InstitutionRef, organization_id)
    if ref is None:
        ref = InstitutionRef(organization_id=organization_id, name="")
        db.add(ref)
    ref.name = payload.get("name") or ref.name


async def handle_course_published(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    course_id = int(payload["course_id"])
    ref = await db.get(CourseRef, course_id)
    if ref is None:
        ref = CourseRef(course_id=course_id, title="")
        db.add(ref)
    ref.title = payload.get("title") or ref.title
