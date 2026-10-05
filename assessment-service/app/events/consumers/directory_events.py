"""Builds the enrolment and course-structure read-models (app/models/refs.py) from other services' events.

  enrollment.created        {"enrollment_id", "student_user_id", "organization_id", "version_id", ...}   learning-service
  enrollment.removed        {"enrollment_id", "student_user_id", "version_id", ...}
  course.eligible_for_final {"enrollment_id", "version_id", "student_user_id"}
  course.published          catalog-service's full tree: {"course_id", "version_id", "final_test_id", "modules": [...]}
  course.retired            {"course_id", "version_id", ...}

Every handler is an idempotent upsert, and the router additionally records each event id (processed_events).
"""

from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refs import EnrollmentRef, VersionRef, VersionTarget
from app.services.eligibility_service import TEST_TARGET


async def _enrollment(db: AsyncSession, payload: dict[str, Any]) -> EnrollmentRef:
    enrollment_id = int(payload["enrollment_id"])
    ref = await db.get(EnrollmentRef, enrollment_id)
    if ref is None:
        ref = EnrollmentRef(
            enrollment_id=enrollment_id,
            student_user_id=int(payload["student_user_id"]),
            version_id=int(payload["version_id"]),
            organization_id=int(payload["organization_id"]) if payload.get("organization_id") else None,
            active=True,
            eligible_for_final=False,
        )
        db.add(ref)
    return ref


async def handle_enrollment_created(db: AsyncSession, payload: dict[str, Any]) -> None:
    ref = await _enrollment(db, payload)
    ref.active = True
    if payload.get("organization_id"):
        ref.organization_id = int(payload["organization_id"])


async def handle_enrollment_removed(db: AsyncSession, payload: dict[str, Any]) -> None:
    (await _enrollment(db, payload)).active = False


async def handle_eligible_for_final(db: AsyncSession, payload: dict[str, Any]) -> None:
    (await _enrollment(db, payload)).eligible_for_final = True


async def handle_course_published(db: AsyncSession, payload: dict[str, Any]) -> None:
    version_id, course_id = int(payload["version_id"]), int(payload["course_id"])
    ref = await db.get(VersionRef, version_id)
    if ref is None:
        ref = VersionRef(version_id=version_id, course_id=course_id)
        db.add(ref)
    ref.course_id, ref.status = course_id, "published"
    await db.flush()

    targets: set[tuple[str, int]] = {("course", course_id)}
    if payload.get("final_test_id"):
        targets.add((TEST_TARGET, int(payload["final_test_id"])))
    for module in payload.get("modules", []):
        targets.add(("module", int(module["module_id"])))
        if module.get("module_test_id"):
            targets.add((TEST_TARGET, int(module["module_test_id"])))
        for topic in module.get("topics", []):
            targets.add(("topic", int(topic["topic_id"])))
            if topic.get("topic_test_id"):
                targets.add((TEST_TARGET, int(topic["topic_test_id"])))
    await db.execute(delete(VersionTarget).where(VersionTarget.version_id == version_id))
    for target_type, target_id in sorted(targets):
        db.add(VersionTarget(version_id=version_id, target_type=target_type, target_id=target_id))


async def handle_course_retired(db: AsyncSession, payload: dict[str, Any]) -> None:
    ref = await db.get(VersionRef, int(payload["version_id"]))
    if ref is not None:
        ref.status = "retired"  # students already enrolled in it keep their tests
