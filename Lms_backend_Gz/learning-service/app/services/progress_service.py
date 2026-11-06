from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.time import utcnow
from app.domain.enums import EnrollmentStatus, UnlockMode
from app.models.assessment_result import AssessmentResult
from app.models.course_version_ref import CourseVersionRef
from app.models.enrollment import Enrollment
from app.models.item_progress import ItemProgress
from app.services.completion import Completion, compute
from app.services.course_structure_service import CourseStructureService
from app.services.outbox import write_event


class ProgressService:
    """Item/topic/module completion and unlock state (docs/PRODUCT.md §3.1): a topic or module is complete once its
    required items are done **and** its test, if it has one, is passed (the result comes from assessment-service's
    ``attempt.finalized``). Milestone events fire exactly on the transition from incomplete to complete. Unlock mode
    ``drip`` isn't scheduled yet: everything is treated as unlocked once its predecessor is complete, like
    ``sequential`` (see README "Not yet wired").
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ what a student has done

    async def _completed_items(self, enrollment: Enrollment) -> set[int]:
        rows = await self.db.execute(select(ItemProgress.topic_item_id).where(ItemProgress.enrollment_id == enrollment.id))
        return set(rows.scalars().all())

    async def _passed_tests(self, enrollment: Enrollment) -> set[int]:
        rows = await self.db.execute(
            select(AssessmentResult.test_id).where(AssessmentResult.enrollment_id == enrollment.id, AssessmentResult.passed.is_(True))
        )
        return set(rows.scalars().all())

    # ------------------------------------------------------------------ items

    async def complete_item(self, enrollment: Enrollment, topic_item_id: int) -> ItemProgress:
        if enrollment.status != EnrollmentStatus.ACTIVE:
            raise BadRequestError("This enrolment is not active.", code="ENROLLMENT_NOT_ACTIVE")

        version = await CourseStructureService(self.db).get_full_tree(enrollment.batch.version_id)
        item_ids = {item.topic_item_id for module in version.modules for topic in module.topics for item in topic.items}
        if topic_item_id not in item_ids:
            raise NotFoundError("This item is not part of the enrolled course.", code="TOPIC_ITEM_NOT_FOUND")

        existing = (
            await self.db.execute(
                select(ItemProgress).where(
                    ItemProgress.enrollment_id == enrollment.id, ItemProgress.topic_item_id == topic_item_id
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing  # idempotent: already marked complete

        completed = await self._completed_items(enrollment)
        passed = await self._passed_tests(enrollment)
        before = compute(version, completed, passed)

        progress = ItemProgress(enrollment_id=enrollment.id, topic_item_id=topic_item_id, completed_at=utcnow())
        self.db.add(progress)
        write_event(
            self.db,
            event_type="topic_item.completed",
            aggregate_id=enrollment.id,
            payload={"enrollment_id": str(enrollment.public_id), "topic_item_id": str(topic_item_id)},
        )
        self._emit_transitions(enrollment, version, before, compute(version, completed | {topic_item_id}, passed))
        await self.db.commit()
        return progress

    # ------------------------------------------------------------------ test results

    async def apply_test_result(
        self, *, enrollment_public_id: int, test_id: int, attempt_id: int, result: str, percent: float, revision: int
    ) -> None:
        """Record a released topic/module test result and emit any milestone it completes. Does not commit."""
        enrollment = (
            await self.db.execute(
                select(Enrollment).where(Enrollment.public_id == enrollment_public_id).options(selectinload(Enrollment.batch))
            )
        ).scalar_one_or_none()
        if enrollment is None or enrollment.status != EnrollmentStatus.ACTIVE:
            return
        stored = (
            await self.db.execute(
                select(AssessmentResult).where(AssessmentResult.enrollment_id == enrollment.id, AssessmentResult.test_id == test_id)
            )
        ).scalar_one_or_none()
        passed_now = result == "passed"
        if stored is not None and stored.attempt_id == attempt_id and revision <= stored.revision:
            return  # a redelivered or older announcement of the same attempt
        if stored is not None and stored.passed and not passed_now and stored.attempt_id != attempt_id:
            return  # a later failing attempt never takes back an earlier pass; only an invalidation of that pass does

        version = await CourseStructureService(self.db).get_full_tree(enrollment.batch.version_id)
        completed = await self._completed_items(enrollment)
        before = compute(version, completed, await self._passed_tests(enrollment))
        if stored is None:
            stored = AssessmentResult(enrollment_id=enrollment.id, test_id=test_id)
            self.db.add(stored)
        stored.passed, stored.percent, stored.attempt_id, stored.revision = passed_now, percent, attempt_id, revision
        await self.db.flush()
        self._emit_transitions(enrollment, version, before, compute(version, completed, await self._passed_tests(enrollment)))

    def _emit_transitions(self, enrollment: Enrollment, version: CourseVersionRef, before: Completion, after: Completion) -> None:
        for topic_id in sorted(after.topics - before.topics):
            write_event(
                self.db,
                event_type="topic.completed",
                aggregate_id=enrollment.id,
                payload={"enrollment_id": str(enrollment.public_id), "topic_id": str(topic_id)},
            )
        for module_id in sorted(after.modules - before.modules):
            write_event(
                self.db,
                event_type="module.completed",
                aggregate_id=enrollment.id,
                payload={"enrollment_id": str(enrollment.public_id), "module_id": str(module_id)},
            )
        if after.all_modules and not before.all_modules:
            write_event(
                self.db,
                event_type="course.eligible_for_final",
                aggregate_id=enrollment.id,
                payload={
                    "enrollment_id": str(enrollment.public_id),
                    "version_id": str(version.version_id),
                    "student_user_id": str(enrollment.student_user_id),
                },
            )

    # ------------------------------------------------------------------ unlock state

    async def unlock_state(self, enrollment: Enrollment) -> dict[str, Any]:
        version = await CourseStructureService(self.db).get_full_tree(enrollment.batch.version_id)
        completed_ids = await self._completed_items(enrollment)
        passed = await self._passed_tests(enrollment)
        done = compute(version, completed_ids, passed)

        modules_out = []
        previous_module_complete = True
        for module in version.modules:
            topics_out = []
            previous_topic_complete = True
            for topic in module.topics:
                required_ids = {item.topic_item_id for item in topic.items if item.required}
                topic_complete = topic.topic_id in done.topics
                sequential_unlock = version.unlock_mode != UnlockMode.SEQUENTIAL or previous_topic_complete
                topics_out.append(
                    {
                        "topic_id": topic.topic_id,
                        "title": topic.title,
                        "position": topic.position,
                        "unlocked": bool(previous_module_complete and sequential_unlock),
                        "completed": topic_complete,
                        "completed_items": len(required_ids & completed_ids),
                        "required_items": len(required_ids),
                        "test_required": topic.topic_test_id is not None,
                        "test_passed": topic.topic_test_id is not None and topic.topic_test_id in passed,
                        "items": [
                            {
                                "topic_item_id": item.topic_item_id,
                                "title": item.title,
                                "item_type": item.item_type,
                                "position": item.position,
                                "required": item.required,
                                "completed": item.topic_item_id in completed_ids,
                            }
                            for item in topic.items
                        ],
                    }
                )
                previous_topic_complete = topic_complete
            module_complete = module.module_id in done.modules
            modules_out.append(
                {
                    "module_id": module.module_id,
                    "title": module.title,
                    "position": module.position,
                    "unlocked": previous_module_complete,
                    "completed": module_complete,
                    "test_required": module.module_test_id is not None,
                    "test_passed": module.module_test_id is not None and module.module_test_id in passed,
                    "topics": topics_out,
                }
            )
            previous_module_complete = previous_module_complete and module_complete

        return {"modules": modules_out, "eligible_for_final": previous_module_complete}
