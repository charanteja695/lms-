"""The question bank: authoring, versions and the review lifecycle (docs/PRODUCT.md §3.2, §5.1).

A question is a stable identity with immutable versions. Only one version at a time is open (draft or in review);
approving it publishes it and supersedes the previous one. Tests draw the *published* version, and attempts pin the
version they were served, so approving an edit never changes a paper already in front of a student.
"""

import uuid

from lms_common.pagination import contains_pattern, paginate
from sqlalchemy import and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.db.session import flush_or_conflict
from app.domain.enums import IdempotentScope, QuestionStatus, QuestionType, TagType, TestStatus, VersionStatus
from app.models.question import Question, QuestionStats, QuestionVersion, QuestionVersionTag
from app.models.test import SectionSlot, Test
from app.permissions.policy import (
    author_organization,
    can_author_owned_by,
    can_read_owned_by,
    can_review_owned_by,
    is_super_admin,
)
from app.schemas.common import QuestionQuery
from app.schemas.question import QuestionCreate, QuestionUpdate
from app.services.idempotency_service import IdempotencyService, request_hash
from app.validators.question_content import validate_question_content

_OPEN = (VersionStatus.DRAFT, VersionStatus.IN_REVIEW)


def _tag_rows(version_id: uuid.UUID, skills: list[str], topics: list[str], tags: list[str]) -> list[QuestionVersionTag]:
    rows: dict[tuple[str, str], QuestionVersionTag] = {}
    for tag_type, values in ((TagType.SKILL, skills), (TagType.TOPIC, topics), (TagType.TAG, tags)):
        for value in values:
            normalised = value.strip().lower()
            rows[(tag_type, normalised)] = QuestionVersionTag(version_id=version_id, tag_type=tag_type, value=normalised)
    return list(rows.values())


def tags_of(version: QuestionVersion, tag_type: TagType) -> list[str]:
    return sorted(tag.value for tag in version.tags if tag.tag_type == tag_type)


class QuestionService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    # ------------------------------------------------------------------ reads

    async def get(self, public_id: int, auth: AccessTokenClaims | None = None) -> Question:
        """The question with every version and tag loaded. With ``auth``, the caller must be allowed to read it."""
        question = (
            await self.db.execute(
                select(Question)
                .where(Question.public_id == public_id)
                .options(selectinload(Question.versions).selectinload(QuestionVersion.tags))
            )
        ).scalar_one_or_none()
        # Not found rather than forbidden: another owner's question must not be confirmable by its id.
        if question is None or (auth is not None and not can_read_owned_by(auth, question.organization_id)):
            raise NotFoundError("Question not found.", code="QUESTION_NOT_FOUND")
        return question

    @staticmethod
    def current(question: Question) -> QuestionVersion | None:
        return next((v for v in question.versions if v.version_no == question.current_version_no), None)

    @staticmethod
    def working(question: Question) -> QuestionVersion | None:
        return next((v for v in reversed(question.versions) if v.status in _OPEN), None)

    async def list_questions(
        self, query: QuestionQuery, auth: AccessTokenClaims
    ) -> tuple[list[Question], dict[uuid.UUID, QuestionVersion], int, bool]:
        scope = self._bank_scope(auth, query.organization_id)
        latest = QuestionVersion
        stmt = (
            select(Question)
            .join(latest, and_(latest.question_id == Question.id, latest.version_no == Question.latest_version_no))
            .where(Question.organization_id.is_(None) if scope is None else Question.organization_id == scope)
        )
        if query.question_type:
            stmt = stmt.where(Question.question_type == query.question_type)
        if query.status:
            stmt = stmt.where(Question.status == query.status)
        if query.version_status:
            stmt = stmt.where(latest.status == query.version_status)
        if query.difficulty_min:
            stmt = stmt.where(latest.difficulty >= query.difficulty_min)
        if query.difficulty_max:
            stmt = stmt.where(latest.difficulty <= query.difficulty_max)
        if query.bloom:
            stmt = stmt.where(latest.bloom == query.bloom)
        for tag_type, value in ((TagType.SKILL, query.skill), (TagType.TOPIC, query.topic), (TagType.TAG, query.tag)):
            if value:
                stmt = stmt.where(
                    exists().where(
                        QuestionVersionTag.version_id == latest.id,
                        QuestionVersionTag.tag_type == tag_type,
                        QuestionVersionTag.value == value.strip().lower(),
                    )
                )
        if query.search:
            stmt = stmt.where(latest.text.ilike(contains_pattern(query.search), escape="\\"))
        order = Question.created_at.asc() if query.sort_order == "asc" else Question.created_at.desc()
        stmt = stmt.order_by(order, Question.id)

        questions, total, is_exact = await paginate(self.db, stmt, query.page, query.per_page)
        versions: dict[uuid.UUID, QuestionVersion] = {}
        if questions:
            rows = (
                await self.db.execute(
                    select(QuestionVersion)
                    .where(
                        QuestionVersion.question_id.in_([q.id for q in questions]),
                    )
                    .options(selectinload(QuestionVersion.tags))
                )
            ).scalars()
            by_question = {q.id: q.latest_version_no for q in questions}
            versions = {v.question_id: v for v in rows if v.version_no == by_question.get(v.question_id)}
        return questions, versions, total, is_exact

    @staticmethod
    def _bank_scope(auth: AccessTokenClaims, requested_org: int | None) -> int | None:
        """Whose bank the caller browses: super admins pick, an employer member gets their employer's, platform
        staff get the platform's."""
        if is_super_admin(auth):
            return requested_org
        if auth.organization_id is not None and auth.role in {"employer_admin", "recruiter"}:
            return auth.organization_id
        if can_read_owned_by(auth, None):
            return None
        raise PermissionDeniedError()

    async def stats(self, question: Question) -> QuestionStats | None:
        return await self.db.get(QuestionStats, question.id)

    # ------------------------------------------------------------------ writes

    async def create(self, data: QuestionCreate, auth: AccessTokenClaims, key: str | None = None) -> Question:
        allowed, owner = author_organization(auth)
        if not allowed:
            raise PermissionDeniedError()
        idempotency = IdempotencyService(self.db)
        payload_hash = request_hash(data.model_dump(mode="json"))
        if key:
            existing = await idempotency.find(auth.user_id, IdempotentScope.QUESTION, key, payload_hash)
            if existing is not None:
                return await self.get(existing)
        question = self._build(data, auth, owner)
        self.db.add(question)
        if key:
            idempotency.remember(auth.user_id, IdempotentScope.QUESTION, key, payload_hash, question.public_id)
        await flush_or_conflict(self.db)
        await self.db.commit()
        return await self.get(question.public_id)

    def _build(self, data: QuestionCreate, auth: AccessTokenClaims, owner: int | None) -> Question:
        body, answer_key = validate_question_content(data.question_type, data.body, data.answer_key, self.settings)
        question = Question(
            public_id=new_public_id(),
            question_type=data.question_type,
            organization_id=owner,
            created_by=auth.user_id,
            latest_version_no=1,
        )
        question.id = uuid.uuid4()
        version = QuestionVersion(
            question_id=question.id,
            version_no=1,
            status=VersionStatus.DRAFT,
            text=data.text,
            body=body,
            answer_key=answer_key,
            explanation=data.explanation,
            default_marks=data.default_marks,
            difficulty=data.difficulty,
            bloom=data.bloom,
            created_by=auth.user_id,
        )
        version.id = uuid.uuid4()
        version.tags = _tag_rows(version.id, data.skills, data.topics, data.tags)
        question.versions = [version]
        return question

    async def bulk_create(
        self, items: list[QuestionCreate], auth: AccessTokenClaims, key: str | None = None
    ) -> list[tuple[int, Question | None, Exception | None]]:
        """Each item is created or refused on its own; one bad question does not sink the batch."""
        allowed, owner = author_organization(auth)
        if not allowed:
            raise PermissionDeniedError()
        if len(items) > self.settings.BULK_IMPORT_MAX_QUESTIONS:
            raise BadRequestError(
                f"Import at most {self.settings.BULK_IMPORT_MAX_QUESTIONS} questions per request.", code="TOO_MANY_QUESTIONS"
            )
        idempotency = IdempotencyService(self.db)
        payload_hash = request_hash({"questions": [item.model_dump(mode="json") for item in items]})
        if key:
            existing = await idempotency.find(auth.user_id, IdempotentScope.IMPORT, key, payload_hash)
            if existing is not None:
                raise ConflictError("This import was already processed.", code="IMPORT_ALREADY_PROCESSED")
        outcome: list[tuple[int, Question | None, Exception | None]] = []
        built: list[Question] = []
        for index, item in enumerate(items):
            try:
                question = self._build(item, auth, owner)
            except ValidationFailedError as exc:
                outcome.append((index, None, exc))
            else:
                built.append(question)
                self.db.add(question)
                outcome.append((index, question, None))
        if key:
            idempotency.remember(auth.user_id, IdempotentScope.IMPORT, key, payload_hash, new_public_id())
        await flush_or_conflict(self.db)
        await self.db.commit()
        return outcome

    async def update(self, question: Question, data: QuestionUpdate, auth: AccessTokenClaims) -> Question:
        self._require_author(question, auth)
        version = self.working(question)
        if version is not None and version.status == VersionStatus.IN_REVIEW:
            raise ConflictError(
                "This question is in review. Ask the reviewer to reject it before editing.", code="VERSION_IN_REVIEW"
            )
        if version is None:  # editing a published question: a new draft that starts as a copy of the live version
            current = self.current(question)
            if current is None:
                raise ConflictError("This question has no version to edit.", code="NO_VERSION")
            version = self._copy_as_draft(question, current, auth)

        fields = data.model_dump(exclude_unset=True)
        if "body" in fields or "answer_key" in fields:
            body, answer_key = validate_question_content(
                QuestionType(question.question_type),
                fields.get("body", version.body),
                fields.get("answer_key", version.answer_key),
                self.settings,
            )
            version.body, version.answer_key = body, answer_key
        for name in ("text", "explanation", "default_marks", "difficulty", "bloom"):
            if name in fields:
                setattr(version, name, fields[name])
        if any(name in fields for name in ("skills", "topics", "tags")):
            version.tags = _tag_rows(
                version.id,
                fields["skills"] if "skills" in fields else tags_of(version, TagType.SKILL),
                fields["topics"] if "topics" in fields else tags_of(version, TagType.TOPIC),
                fields["tags"] if "tags" in fields else tags_of(version, TagType.TAG),
            )
        version.review_note = None
        await flush_or_conflict(self.db)
        await self.db.commit()
        return await self.get(question.public_id)

    def _copy_as_draft(self, question: Question, source: QuestionVersion, auth: AccessTokenClaims) -> QuestionVersion:
        draft = QuestionVersion(
            question_id=question.id,
            version_no=question.latest_version_no + 1,
            status=VersionStatus.DRAFT,
            text=source.text,
            body=source.body,
            answer_key=source.answer_key,
            explanation=source.explanation,
            default_marks=source.default_marks,
            difficulty=source.difficulty,
            bloom=source.bloom,
            created_by=auth.user_id,
        )
        draft.id = uuid.uuid4()
        draft.tags = [QuestionVersionTag(version_id=draft.id, tag_type=t.tag_type, value=t.value) for t in source.tags]
        question.latest_version_no = draft.version_no
        question.versions.append(draft)
        return draft

    async def submit(self, question: Question, auth: AccessTokenClaims) -> Question:
        self._require_author(question, auth)
        version = self.working(question)
        if version is None or version.status != VersionStatus.DRAFT:
            raise ConflictError("Only a draft can be submitted for review.", code="VERSION_NOT_DRAFT")
        validate_question_content(QuestionType(question.question_type), version.body, version.answer_key, self.settings)
        version.status = VersionStatus.IN_REVIEW
        version.submitted_at = utcnow()
        await self.db.commit()
        return await self.get(question.public_id)

    async def approve(self, question: Question, auth: AccessTokenClaims, note: str | None) -> Question:
        self._require_reviewer(question, auth)
        version = self.working(question)
        if version is None or version.status != VersionStatus.IN_REVIEW:
            raise ConflictError("Only a version in review can be approved.", code="VERSION_NOT_IN_REVIEW")
        if version.created_by == auth.user_id and not is_super_admin(auth):
            raise PermissionDeniedError("Someone other than the author must approve this.", code="SELF_REVIEW_NOT_ALLOWED")
        for other in question.versions:
            if other.status == VersionStatus.PUBLISHED:
                other.status = VersionStatus.SUPERSEDED
        version.status = VersionStatus.PUBLISHED
        version.reviewed_by, version.reviewed_at, version.published_at = auth.user_id, utcnow(), utcnow()
        version.review_note = note
        question.current_version_no = version.version_no
        await self.db.commit()
        return await self.get(question.public_id)

    async def reject(self, question: Question, auth: AccessTokenClaims, note: str) -> Question:
        self._require_reviewer(question, auth)
        version = self.working(question)
        if version is None or version.status != VersionStatus.IN_REVIEW:
            raise ConflictError("Only a version in review can be rejected.", code="VERSION_NOT_IN_REVIEW")
        version.status = VersionStatus.DRAFT
        version.reviewed_by, version.reviewed_at, version.review_note = auth.user_id, utcnow(), note
        await self.db.commit()
        return await self.get(question.public_id)

    async def discard_draft(self, question: Question, auth: AccessTokenClaims) -> Question:
        """Drop an unpublished edit of a live question (a question's first version cannot be discarded)."""
        self._require_author(question, auth)
        version = self.working(question)
        if version is None or version.status != VersionStatus.DRAFT or question.current_version_no is None:
            raise ConflictError("There is no draft edit to discard.", code="NO_DRAFT_EDIT")
        question.versions.remove(version)
        question.latest_version_no = question.current_version_no
        await self.db.commit()
        return await self.get(question.public_id)

    async def retire(self, question: Question, auth: AccessTokenClaims) -> Question:
        self._require_reviewer(question, auth)
        in_use = (
            await self.db.execute(
                select(Test.public_id)
                .join(SectionSlot, SectionSlot.test_id == Test.id)
                .where(SectionSlot.question_id == question.id, Test.status == TestStatus.PUBLISHED)
                .distinct()
            )
        ).scalars().all()
        if in_use:
            raise ConflictError(
                "A published test uses this question; retire the test first.",
                code="QUESTION_IN_USE",
                details=[{"field": "test_id", "code": "IN_USE", "message": str(test_id)} for test_id in in_use],
            )
        question.status = QuestionStatus.RETIRED
        await self.db.commit()
        return await self.get(question.public_id)

    async def restore(self, question: Question, auth: AccessTokenClaims) -> Question:
        self._require_reviewer(question, auth)
        question.status = QuestionStatus.ACTIVE
        await self.db.commit()
        return await self.get(question.public_id)

    # ------------------------------------------------------------------ rules

    @staticmethod
    def _require_author(question: Question, auth: AccessTokenClaims) -> None:
        if not can_author_owned_by(auth, question.organization_id):
            raise PermissionDeniedError()

    @staticmethod
    def _require_reviewer(question: Question, auth: AccessTokenClaims) -> None:
        if not can_review_owned_by(auth, question.organization_id):
            raise PermissionDeniedError()
