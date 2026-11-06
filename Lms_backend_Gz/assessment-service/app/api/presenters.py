"""Maps domain objects to response schemas. Kept out of the endpoints so they stay thin, and free of rules:
everything decided here is presentation (what a student may see, and when), never business logic."""

import uuid
from datetime import datetime

from app.core.time import utcnow
from app.domain.enums import AttemptStatus, ReviewPolicy, TagType
from app.models.attempt import Attempt
from app.models.question import Question, QuestionStats, QuestionVersion
from app.models.test import Test
from app.schemas.attempt import AttemptStateOut, SectionStateOut
from app.schemas.question import QuestionListItem, QuestionOut, QuestionStatsOut, QuestionVersionOut
from app.schemas.test import SectionOut, SlotOut, TestOut
from app.services import clock
from app.services.clock import SectionClock
from app.services.question_service import QuestionService, tags_of


def version_out(version: QuestionVersion) -> QuestionVersionOut:
    return QuestionVersionOut(
        version_no=version.version_no,
        status=version.status,
        text=version.text,
        body=version.body,
        answer_key=version.answer_key,
        explanation=version.explanation,
        default_marks=version.default_marks,
        difficulty=version.difficulty,
        bloom=version.bloom,
        skills=tags_of(version, TagType.SKILL),
        topics=tags_of(version, TagType.TOPIC),
        tags=tags_of(version, TagType.TAG),
        review_note=version.review_note,
        created_by=version.created_by,
        created_at=version.created_at,
        submitted_at=version.submitted_at,
        reviewed_by=version.reviewed_by,
        reviewed_at=version.reviewed_at,
        published_at=version.published_at,
    )


def question_out(question: Question, stats: QuestionStats | None = None) -> QuestionOut:
    current, working = QuestionService.current(question), QuestionService.working(question)
    return QuestionOut(
        question_id=question.public_id,
        question_type=question.question_type,
        status=question.status,
        organization_id=question.organization_id,
        current_version_no=question.current_version_no,
        latest_version_no=question.latest_version_no,
        created_by=question.created_by,
        created_at=question.created_at,
        updated_at=question.updated_at,
        current=version_out(current) if current else None,
        working=version_out(working) if working else None,
        stats=QuestionStatsOut.model_validate(stats) if stats else None,
    )


def question_list_item(question: Question, version: QuestionVersion) -> QuestionListItem:
    return QuestionListItem(
        question_id=question.public_id,
        question_type=question.question_type,
        status=question.status,
        current_version_no=question.current_version_no,
        latest_version_no=question.latest_version_no,
        latest_version_status=version.status,
        text=version.text,
        difficulty=version.difficulty,
        bloom=version.bloom,
        default_marks=version.default_marks,
        skills=tags_of(version, TagType.SKILL),
        topics=tags_of(version, TagType.TOPIC),
        tags=tags_of(version, TagType.TAG),
        created_at=question.created_at,
    )


def definition_out(test: Test, question_ids: dict[uuid.UUID, int]) -> TestOut:
    """The author view: sections and slots, with the public id of each fixed question."""
    return TestOut(
        **{name: getattr(test, name) for name in TestOut.model_fields if name not in {"test_id", "sections"} and hasattr(test, name)},
        public_id=test.public_id,
        sections=[
            SectionOut(
                public_id=section.public_id,
                position=section.position,
                title=section.title,
                instructions=section.instructions,
                time_limit_minutes=section.time_limit_minutes,
                slots=[
                    SlotOut(
                        position=slot.position,
                        slot_type=slot.slot_type,
                        question_id=question_ids.get(slot.question_id) if slot.question_id else None,
                        criteria=slot.criteria,
                        count=slot.count,
                        marks=slot.marks,
                    )
                    for slot in section.slots
                ],
            )
            for section in test.sections
        ],
    )




def section_states(clocks: list[SectionClock], titles: dict[int, str], limits: dict[int, int | None]) -> list[SectionStateOut]:
    current = clock.current(clocks)
    return [
        SectionStateOut(
            section_id=c.section_id,
            position=c.position,
            title=titles.get(c.position, ""),
            time_limit_minutes=limits.get(c.position),
            started_at=c.started_at,
            deadline_at=c.deadline_at,
            finished_at=c.finished_at,
            is_current=current is c,
        )
        for c in clocks
    ]


def attempt_state(
    attempt: Attempt,
    test: Test,
    *,
    sections: list[SectionStateOut] | None = None,
    opens_at: datetime | None = None,
    now: datetime | None = None,
) -> AttemptStateOut:
    now = now or utcnow()
    remaining: int | None = None
    if attempt.deadline_at is not None and attempt.status in (AttemptStatus.IN_PROGRESS, AttemptStatus.PAUSED):
        reference = attempt.paused_at if attempt.status == AttemptStatus.PAUSED and attempt.paused_at else now
        remaining = max(0, int((attempt.deadline_at - reference).total_seconds()))
    return AttemptStateOut(
        attempt_id=attempt.public_id,
        test_id=test.public_id,
        test_title=test.title,
        test_kind=test.kind,
        status=attempt.status,
        attempt_no=attempt.attempt_no,
        proctoring_level=test.proctoring_level,
        time_mode=test.time_mode,
        started_at=attempt.started_at,
        deadline_at=attempt.deadline_at,
        remaining_seconds=remaining,
        server_time=now,
        resume_count=attempt.resume_count,
        opens_at=opens_at,
        submitted_at=attempt.submitted_at,
        submit_reason=attempt.submit_reason,
        results_released=attempt.results_visible_at is not None,
        total_questions=test.question_count or 0,
        sections=sections or [],
    )


def wants_review(test: Test) -> bool:
    return test.review_policy == ReviewPolicy.ANSWERS
