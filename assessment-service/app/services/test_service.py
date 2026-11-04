"""Test definitions: authoring, validation and the review lifecycle (docs/PRODUCT.md §3.2, §5.1).

A test is editable while a draft. Submitting runs the full publish validation; approving freezes it (its total
marks and question count are fixed) and announces ``test.published`` so catalog-service can attach it to its
module/topic. To change a published test, clone it into a new draft and retire the old one.
"""

import uuid
from typing import Any

from lms_common.pagination import contains_pattern, paginate
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.db.session import flush_or_conflict
from app.domain.enums import (
    IdempotentScope,
    QuestionStatus,
    QuestionType,
    SlotType,
    TargetType,
    TestKind,
    TestStatus,
    TimeMode,
)
from app.models.question import Question, QuestionVersion
from app.models.test import SectionSlot, Test, TestSection
from app.paper.pool import PoolIndex
from app.permissions.policy import (
    author_organization,
    can_author_owned_by,
    can_manage_exams,
    can_read_owned_by,
    can_review_owned_by,
    is_employer_member,
    is_super_admin,
)
from app.schemas.common import TestQuery
from app.schemas.test import SectionIn, TestCreate, TestUpdate
from app.services.idempotency_service import IdempotencyService, request_hash
from app.services.outbox import write_event

_TARGET_FOR_KIND = {TestKind.TOPIC: TargetType.TOPIC, TestKind.MODULE: TargetType.MODULE, TestKind.FINAL: TargetType.COURSE}
_RULE_FIELDS = (
    "title",
    "description",
    "instructions",
    "time_mode",
    "duration_minutes",
    "pass_mark_percent",
    "max_attempts",
    "cooldown_hours",
    "score_counting",
    "negative_marking_percent",
    "shuffle_questions",
    "shuffle_options",
    "result_visibility",
    "review_policy",
    "proctoring_level",
    "proctoring_screen_share",
    "requires_schedule",
)


def definition_event_payload(test: Test) -> dict[str, Any]:
    return {
        "test_id": str(test.public_id),
        "title": test.title,
        "kind": test.kind,
        "target_type": test.target_type,
        "target_id": str(test.target_id) if test.target_id else None,
        "organization_id": str(test.organization_id) if test.organization_id else None,
        "pass_mark_percent": test.pass_mark_percent,
        "max_attempts": test.max_attempts,
        "cooldown_hours": test.cooldown_hours,
        "time_mode": test.time_mode,
        "duration_minutes": test.duration_minutes,
        "proctoring_level": test.proctoring_level,
        "proctoring_screen_share": test.proctoring_level == "strict" and test.proctoring_screen_share,
        "total_marks": test.total_marks,
        "question_count": test.question_count,
    }




_MCQ_TYPES = frozenset({QuestionType.MCQ_SINGLE, QuestionType.MCQ_MULTI})
_PROGRAM_TYPES = frozenset({QuestionType.CODING})

class TestService:
    __test__ = False

    def __init__(self, db: AsyncSession, settings: Settings, redis: Redis | None = None) -> None:
        self.db = db
        self.settings = settings
        self.redis = redis

    # ------------------------------------------------------------------ reads

    async def get(self, public_id: int, auth: AccessTokenClaims | None = None) -> Test:
        """The test with sections and slots. With ``auth``, the caller must be allowed to read its definition."""
        test = await self.load(public_id)
        if auth is not None and not (can_read_owned_by(auth, test.organization_id) or can_manage_exams(auth)):
            raise NotFoundError("Test not found.", code="TEST_NOT_FOUND")
        return test

    async def load(self, public_id: int) -> Test:
        test = (
            await self.db.execute(
                select(Test)
                .where(Test.public_id == public_id)
                .options(selectinload(Test.sections).selectinload(TestSection.slots))
            )
        ).scalar_one_or_none()
        if test is None:
            raise NotFoundError("Test not found.", code="TEST_NOT_FOUND")
        return test

    async def question_public_ids(self, test: Test) -> dict[uuid.UUID, int]:
        """Public ids of the fixed questions a test names (its slots hold row ids)."""
        wanted = {slot.question_id for section in test.sections for slot in section.slots if slot.question_id is not None}
        if not wanted:
            return {}
        rows = await self.db.execute(select(Question.id, Question.public_id).where(Question.id.in_(wanted)))
        return {question_id: public_id for question_id, public_id in rows.all()}

    async def list_tests(self, query: TestQuery, auth: AccessTokenClaims) -> tuple[list[Test], int, bool]:
        if is_super_admin(auth):
            owner_filter = Test.organization_id == query.organization_id if query.organization_id else None
        elif is_employer_member(auth):
            owner_filter = Test.organization_id == auth.organization_id
        elif can_read_owned_by(auth, None) or can_manage_exams(auth):
            owner_filter = Test.organization_id.is_(None)
        else:
            raise PermissionDeniedError()
        stmt = select(Test)
        if owner_filter is not None:
            stmt = stmt.where(owner_filter)
        if query.kind:
            stmt = stmt.where(Test.kind == query.kind)
        if query.status:
            stmt = stmt.where(Test.status == query.status)
        if query.target_id:
            stmt = stmt.where(Test.target_id == query.target_id)
        if query.target_ids:
            stmt = stmt.where(Test.target_id.in_([int(part) for part in query.target_ids.split(",")]))
        if query.search:
            stmt = stmt.where(Test.title.ilike(contains_pattern(query.search), escape="\\"))
        stmt = stmt.order_by(Test.created_at.asc() if query.sort_order == "asc" else Test.created_at.desc(), Test.id)
        rows, total, is_exact = await paginate(self.db, stmt, query.page, query.per_page)
        return rows, total, is_exact

    # ------------------------------------------------------------------ authoring

    async def create(self, data: TestCreate, auth: AccessTokenClaims, key: str | None = None) -> Test:
        allowed, owner = author_organization(auth)
        if not allowed:
            raise PermissionDeniedError()
        idempotency = IdempotencyService(self.db)
        payload_hash = request_hash(data.model_dump(mode="json"))
        if key:
            existing = await idempotency.find(auth.user_id, IdempotentScope.TEST, key, payload_hash)
            if existing is not None:
                return await self.get(existing)

        test = Test(
            public_id=new_public_id(),
            organization_id=owner,
            created_by=auth.user_id,
            kind=data.kind,
            **{name: getattr(data, name) for name in _RULE_FIELDS},
        )
        test.id = uuid.uuid4()
        self._apply_target(test, data.kind, data.target_id)
        self.db.add(test)
        await flush_or_conflict(self.db)
        if data.sections:
            await self._write_sections(test, data.sections)
        if key:
            idempotency.remember(auth.user_id, IdempotentScope.TEST, key, payload_hash, test.public_id)
        await flush_or_conflict(self.db)
        await self.db.commit()
        return await self.load(test.public_id)

    async def update(self, test: Test, data: TestUpdate, auth: AccessTokenClaims) -> Test:
        self._require_editable(test, auth)
        fields = data.model_dump(exclude_unset=True)
        kind = fields.pop("kind", None) or test.kind
        target_id = fields.pop("target_id", test.target_id)
        for name in _RULE_FIELDS:
            if name in fields and fields[name] is not None:
                setattr(test, name, fields[name])
        if "duration_minutes" in fields:
            test.duration_minutes = fields["duration_minutes"]
        self._apply_target(test, TestKind(kind), target_id)
        await flush_or_conflict(self.db)
        await self.db.commit()
        return await self.load(test.public_id)

    async def replace_sections(self, test: Test, sections: list[SectionIn], auth: AccessTokenClaims) -> Test:
        self._require_editable(test, auth)
        if len(sections) > self.settings.MAX_SECTIONS_PER_TEST:
            raise ValidationFailedError(
                details=[{"field": "sections", "code": "TOO_MANY_ITEMS", "message": f"At most {self.settings.MAX_SECTIONS_PER_TEST} sections"}]
            )
        questions = await self._questions_for(test, sections)
        existing_sections = list(test.sections)

        for i, section_in in enumerate(sections, start=1):
            if i <= len(existing_sections):
                section = existing_sections[i - 1]
                section.position = i
                section.title = section_in.title
                section.instructions = section_in.instructions
                section.time_limit_minutes = section_in.time_limit_minutes
                for slot in list(section.slots):
                    await self.db.delete(slot)
                await self.db.flush()
            else:
                section = TestSection(
                    public_id=new_public_id(),
                    test_id=test.id,
                    position=i,
                    title=section_in.title,
                    instructions=section_in.instructions,
                    time_limit_minutes=section_in.time_limit_minutes,
                )
                section.id = uuid.uuid4()
                self.db.add(section)
                await self.db.flush()

            for slot_position, slot_in in enumerate(section_in.slots, start=1):
                question = questions.get(slot_in.question_id) if slot_in.question_id else None
                marks = slot_in.marks or (question[1] if question else 1.0)
                self.db.add(
                    SectionSlot(
                        section_id=section.id,
                        test_id=test.id,
                        position=slot_position,
                        slot_type=slot_in.slot_type,
                        question_id=question[0].id if question else None,
                        criteria=slot_in.criteria.model_dump(exclude_none=True, mode="json") if slot_in.criteria else None,
                        count=slot_in.count,
                        marks=marks,
                    )
                )

        if len(existing_sections) > len(sections):
            for section in existing_sections[len(sections):]:
                for slot in list(section.slots):
                    await self.db.delete(slot)
                try:
                    await self.db.delete(section)
                except Exception:
                    pass

        await flush_or_conflict(self.db)
        if test.status == TestStatus.PUBLISHED:
            issues, total, count = await self.validate(test)
            if not issues and total is not None and count is not None:
                test.total_marks, test.question_count = total, count
        await self.db.commit()
        return await self.load(test.public_id)

    async def delete_draft(self, test: Test, auth: AccessTokenClaims) -> None:
        self._require_editable(test, auth)
        await self.db.delete(test)
        await self.db.commit()

    async def clone(self, test: Test, auth: AccessTokenClaims) -> Test:
        allowed, owner = author_organization(auth)
        if not allowed or not can_read_owned_by(auth, test.organization_id) or owner != test.organization_id:
            if not is_super_admin(auth):
                raise PermissionDeniedError()
            owner = test.organization_id
        copy = Test(
            public_id=new_public_id(),
            organization_id=owner,
            created_by=auth.user_id,
            kind=test.kind,
            target_type=test.target_type,
            target_id=test.target_id,
            **{name: getattr(test, name) for name in _RULE_FIELDS if name != "title"},
            title=f"{test.title} (copy)"[:200],
        )
        copy.id = uuid.uuid4()
        self.db.add(copy)
        await self.db.flush()
        for section in test.sections:
            new_section = TestSection(
                public_id=new_public_id(),
                test_id=copy.id,
                position=section.position,
                title=section.title,
                instructions=section.instructions,
                time_limit_minutes=section.time_limit_minutes,
            )
            new_section.id = uuid.uuid4()
            self.db.add(new_section)
            await self.db.flush()
            for slot in section.slots:
                self.db.add(
                    SectionSlot(
                        section_id=new_section.id,
                        test_id=copy.id,
                        position=slot.position,
                        slot_type=slot.slot_type,
                        question_id=slot.question_id,
                        criteria=slot.criteria,
                        count=slot.count,
                        marks=slot.marks,
                    )
                )
        await self.db.commit()
        return await self.load(copy.public_id)

    def _apply_target(self, test: Test, kind: TestKind, target_id: int | None) -> None:
        details: list[dict[str, Any]] = []
        expected = _TARGET_FOR_KIND.get(kind)
        if expected is None and target_id is not None:
            details.append({"field": "target_id", "code": "NOT_ALLOWED", "message": f"A {kind} test has no target"})
        if test.organization_id is not None and kind != TestKind.HIRING:
            details.append({"field": "kind", "code": "HIRING_ONLY", "message": "An employer can only author hiring tests"})
        if details:
            raise ValidationFailedError(details=details)
        test.kind = kind
        test.target_type = expected
        test.target_id = target_id if expected else None

    async def _write_sections(self, test: Test, sections: list[SectionIn]) -> None:
        if len(sections) > self.settings.MAX_SECTIONS_PER_TEST:
            raise ValidationFailedError(
                details=[{"field": "sections", "code": "TOO_MANY_ITEMS", "message": f"At most {self.settings.MAX_SECTIONS_PER_TEST} sections"}]
            )
        questions = await self._questions_for(test, sections)
        for position, section_in in enumerate(sections, start=1):
            section = TestSection(
                public_id=new_public_id(),
                test_id=test.id,
                position=position,
                title=section_in.title,
                instructions=section_in.instructions,
                time_limit_minutes=section_in.time_limit_minutes,
            )
            section.id = uuid.uuid4()
            self.db.add(section)
            await self.db.flush()
            for slot_position, slot_in in enumerate(section_in.slots, start=1):
                question = questions.get(slot_in.question_id) if slot_in.question_id else None
                marks = slot_in.marks or (question[1] if question else 1.0)
                self.db.add(
                    SectionSlot(
                        section_id=section.id,
                        test_id=test.id,
                        position=slot_position,
                        slot_type=slot_in.slot_type,
                        question_id=question[0].id if question else None,
                        criteria=slot_in.criteria.model_dump(exclude_none=True, mode="json") if slot_in.criteria else None,
                        count=slot_in.count,
                        marks=marks,
                    )
                )

    async def _questions_for(self, test: Test, sections: list[SectionIn]) -> dict[int, tuple[Question, float]]:
        """The fixed questions a set of sections names: each must exist in this test's owner's bank. Returns the
        question with its default marks (used when a slot gives none)."""
        wanted: set[int] = set()
        for section in sections:
            for slot in section.slots:
                if slot.question_id is not None:
                    wanted.add(slot.question_id)
        if not wanted:
            return {}
        rows = (
            await self.db.execute(
                select(Question, QuestionVersion.default_marks)
                .join(QuestionVersion, (QuestionVersion.question_id == Question.id) & (QuestionVersion.version_no == Question.latest_version_no))
                .where(Question.public_id.in_(wanted), Question.organization_id.is_(None) if test.organization_id is None else Question.organization_id == test.organization_id)
            )
        ).all()
        found = {question.public_id: (question, float(marks)) for question, marks in rows}
        missing = sorted(wanted - set(found))
        if missing:
            raise ValidationFailedError(
                details=[
                    {"field": "sections", "code": "QUESTION_NOT_FOUND", "message": f"Question {question_id} is not in this test owner's bank"}
                    for question_id in missing
                ]
            )
        return found

    # ------------------------------------------------------------------ validation

    async def validate(self, test: Test) -> tuple[list[dict[str, Any]], float | None, int | None]:
        """Everything that must hold before a test may be published. Returns (issues, total marks, question count)."""
        issues, total, count, _ = await self.validate_with_composition(test)
        return issues, total, count

    def composition_rule(self, test: Test) -> tuple[int, int] | None:
        """(multiple-choice, programs) a course test must hold at least; None when its kind has no such rule."""
        if test.kind == TestKind.TOPIC:
            return self.settings.TOPIC_TEST_MIN_MCQ, self.settings.TOPIC_TEST_MIN_PROGRAMS
        if test.kind == TestKind.FINAL:
            return self.settings.FINAL_TEST_MIN_MCQ, self.settings.FINAL_TEST_MIN_PROGRAMS
        return None

    async def validate_with_composition(
        self, test: Test
    ) -> tuple[list[dict[str, Any]], float | None, int | None, dict[str, int]]:
        """``validate`` plus how many multiple-choice questions and programs the paper holds (for the builder)."""
        issues: list[dict[str, Any]] = []

        def issue(field: str, code: str, message: str) -> None:
            issues.append({"field": field, "code": code, "message": message})

        sections = list(test.sections)
        if not sections:
            issue("sections", "NO_SECTIONS", "Add at least one section with questions")
        if test.kind in _TARGET_FOR_KIND and test.target_id is None:
            issue("target_id", "REQUIRED", f"A {test.kind} test needs the {test.target_type} it belongs to")
        if test.time_mode == TimeMode.OVERALL and not test.duration_minutes:
            issue("duration_minutes", "REQUIRED", "Set the duration for overall timing")
        if test.time_mode == TimeMode.PER_SECTION:
            for section in sections:
                if not section.time_limit_minutes:
                    issue(f"sections[{section.position}].time_limit_minutes", "REQUIRED", "Every section needs a time limit")
        if test.organization_id is not None and test.kind != TestKind.HIRING:
            issue("kind", "HIRING_ONLY", "An employer can only publish hiring tests")

        fixed_ids = {slot.question_id for section in sections for slot in section.slots if slot.question_id is not None}
        fixed_questions: dict[uuid.UUID, Question] = {}
        if fixed_ids:
            fixed_questions = {
                q.id: q for q in (await self.db.execute(select(Question).options(selectinload(Question.versions)).where(Question.id.in_(fixed_ids)))).scalars()
            }
        pools = PoolIndex(self.db, None, self.settings)
        seen_fixed: set[uuid.UUID] = set()
        total_marks = 0.0
        question_count = 0
        mcq_count = 0
        program_count = 0
        for section in sections:
            for slot in section.slots:
                where = f"sections[{section.position}].slots[{slot.position}]"
                if slot.slot_type == SlotType.FIXED:
                    question = fixed_questions.get(slot.question_id) if slot.question_id else None
                    if question is None or question.organization_id != test.organization_id:
                        issue(where, "QUESTION_NOT_FOUND", "The question is missing from this test owner's bank")
                    elif question.status != QuestionStatus.ACTIVE or question.current_version_no is None:
                        issue(where, "QUESTION_UNAVAILABLE", f"Question {question.public_id} is retired or not yet approved")
                    elif question.id in seen_fixed:
                        issue(where, "DUPLICATE_QUESTION", f"Question {question.public_id} is used twice")
                    if slot.question_id is not None:
                        seen_fixed.add(slot.question_id)
                    if question is not None:
                        curr_v = next((v for v in question.versions if v.version_no == question.current_version_no), None) or (question.versions[-1] if question.versions else None)
                        v_body = curr_v.body if curr_v and curr_v.body else {}
                        if v_body.get("sync_status") == "not_synced" or (question.question_type in _PROGRAM_TYPES and not v_body.get("problem_id")):
                            issue(where, "PROBLEM_NOT_SYNCED", f"Programming problem for question {question.public_id} is not synced")
                        mcq_count += question.question_type in _MCQ_TYPES
                        program_count += question.question_type in _PROGRAM_TYPES
                    question_count += 1
                    total_marks += slot.marks
                else:
                    available = [c for c in await pools.eligible(test.organization_id, slot.criteria or {}) if c[0] not in fixed_ids]
                    if len(available) < slot.count:
                        issue(where, "POOL_TOO_SMALL", f"The pool has {len(available)} eligible questions but draws {slot.count}")
                    # a pool counts towards a kind only when it can draw nothing else
                    types = set((slot.criteria or {}).get("types") or [])
                    if types and types <= _MCQ_TYPES:
                        mcq_count += slot.count
                    elif types and types <= _PROGRAM_TYPES:
                        program_count += slot.count
                    question_count += slot.count
                    total_marks += slot.marks * slot.count
        if question_count > self.settings.MAX_QUESTIONS_PER_TEST:
            issue("sections", "TOO_MANY_QUESTIONS", f"A paper can hold at most {self.settings.MAX_QUESTIONS_PER_TEST} questions")
        if sections and total_marks <= 0:
            issue("sections", "NO_MARKS", "The test has no marks to earn")
        rule = self.composition_rule(test)
        composition = {"multiple_choice": mcq_count, "programs": program_count, "required_multiple_choice": 0, "required_programs": 0}
        if rule is not None:
            min_mcq, min_programs = rule
            composition.update(required_multiple_choice=min_mcq, required_programs=min_programs)
            label = "A topic test" if test.kind == TestKind.TOPIC else "The final test"
            if mcq_count < min_mcq:
                issue("sections", "TOO_FEW_MCQ", f"{label} needs at least {min_mcq} multiple-choice questions; it has {mcq_count}")
            if program_count < min_programs:
                issue("sections", "TOO_FEW_PROGRAMS", f"{label} needs at least {min_programs} programs; it has {program_count}")
        return issues, (round(total_marks, 4) if sections else None), (question_count if sections else None), composition

    # ------------------------------------------------------------------ lifecycle

    async def submit(self, test: Test, auth: AccessTokenClaims) -> Test:
        self._require_editable(test, auth)
        issues, total, count = await self.validate(test)
        if issues:
            raise ValidationFailedError("The test is not ready to be reviewed.", details=issues)
        if test.status == TestStatus.PUBLISHED:
            test.total_marks, test.question_count = total, count
            await self.db.commit()
            return await self.load(test.public_id)
        test.status = TestStatus.IN_REVIEW
        test.submitted_at = utcnow()
        test.total_marks, test.question_count = total, count
        test.review_note = None
        await self.db.commit()
        return await self.load(test.public_id)

    async def approve(self, test: Test, auth: AccessTokenClaims, note: str | None) -> Test:
        self._require_reviewer(test, auth)
        if test.status not in (TestStatus.IN_REVIEW, TestStatus.PUBLISHED):
            raise ConflictError("Only a test in review or published can be approved.", code="TEST_NOT_IN_REVIEW")
        if test.created_by == auth.user_id and not is_super_admin(auth):
            raise PermissionDeniedError("Someone other than the author must approve this.", code="SELF_REVIEW_NOT_ALLOWED")
        issues, total, count = await self.validate(test)  # the bank may have changed since it was submitted
        if issues:
            raise ValidationFailedError("The test is no longer valid.", details=issues)
        if test.status != TestStatus.PUBLISHED and test.target_id is not None:
            clash = (
                await self.db.execute(
                    select(Test.public_id).where(
                        Test.target_type == test.target_type,
                        Test.target_id == test.target_id,
                        Test.kind == test.kind,
                        Test.status == TestStatus.PUBLISHED,
                        Test.id != test.id,
                    )
                )
            ).scalar_one_or_none()
            if clash is not None:
                raise ConflictError(
                    f"Test {clash} is already published for this {test.target_type}; retire it first.",
                    code="TARGET_ALREADY_HAS_TEST",
                )
        test.status = TestStatus.PUBLISHED
        test.total_marks, test.question_count = total, count
        test.reviewed_by, test.reviewed_at, test.published_at, test.review_note = auth.user_id, utcnow(), utcnow(), note
        write_event(
            self.db, event_type="test.published", aggregate_type="test", aggregate_id=test.id, payload=definition_event_payload(test)
        )
        await self.db.commit()
        return await self.load(test.public_id)

    async def reject(self, test: Test, auth: AccessTokenClaims, note: str) -> Test:
        self._require_reviewer(test, auth)
        if test.status != TestStatus.IN_REVIEW:
            raise ConflictError("Only a test in review can be rejected.", code="TEST_NOT_IN_REVIEW")
        test.status = TestStatus.DRAFT
        test.reviewed_by, test.reviewed_at, test.review_note = auth.user_id, utcnow(), note
        await self.db.commit()
        return await self.load(test.public_id)

    async def retire(self, test: Test, auth: AccessTokenClaims) -> Test:
        self._require_reviewer(test, auth)
        if test.status != TestStatus.PUBLISHED:
            raise ConflictError("Only a published test can be retired.", code="TEST_NOT_PUBLISHED")
        test.status = TestStatus.RETIRED
        test.retired_at = utcnow()
        write_event(
            self.db, event_type="test.retired", aggregate_type="test", aggregate_id=test.id, payload=definition_event_payload(test)
        )
        await self.db.commit()
        return await self.load(test.public_id)

    # ------------------------------------------------------------------ rules

    @staticmethod
    def _require_editable(test: Test, auth: AccessTokenClaims) -> None:
        if not can_author_owned_by(auth, test.organization_id):
            raise PermissionDeniedError()
        if test.status not in (TestStatus.DRAFT, TestStatus.PUBLISHED):
            raise ConflictError(
                "This test cannot be edited.", code="TEST_NOT_EDITABLE"
            )

    @staticmethod
    def _require_reviewer(test: Test, auth: AccessTokenClaims) -> None:
        if not can_review_owned_by(auth, test.organization_id):
            raise PermissionDeniedError()
