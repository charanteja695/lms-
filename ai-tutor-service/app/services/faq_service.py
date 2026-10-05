"""The FAQ (docs/PRODUCT.md §5.5: "Staff can promote good answers to the FAQ").

An entry is written as a draft (typed in, or promoted from a tutor answer and edited), then published; publishing embeds
it so a close question is answered from the entry itself without a model call. Publishing never fails because the embedding
service is down — the entry is simply matched by word overlap until it is re-embedded.
"""

from lms_common.pagination import paginate
from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.gateway import GatewayClient, GatewayError
from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.domain.enums import FaqScope, FaqStatus
from app.models.faq import FaqEntry
from app.models.refs import CourseVersionRef, EnrollmentRef
from app.permissions.policy import can_author, can_manage_faq, can_manage_support, is_institution_staff
from app.rag.similarity import LexicalIndex


class FaqService:
    def __init__(self, db: AsyncSession, settings: Settings, gateway: GatewayClient) -> None:
        self.db = db
        self.settings = settings
        self.gateway = gateway

    async def get(self, public_id: int) -> FaqEntry:
        entry = (await self.db.execute(select(FaqEntry).where(FaqEntry.public_id == public_id))).scalar_one_or_none()
        if entry is None:
            raise NotFoundError("FAQ entry not found.", code="FAQ_NOT_FOUND")
        return entry

    def authorize(self, auth: AccessTokenClaims, scope: str, organization_id: int | None) -> None:
        if not can_manage_faq(auth, scope, organization_id=organization_id):
            raise PermissionDeniedError("You may not manage FAQ entries of this scope.", code="FAQ_SCOPE_FORBIDDEN")

    @staticmethod
    def _check_scope(scope: str, organization_id: int | None, course_id: int | None) -> None:
        if scope == FaqScope.PLATFORM and (organization_id or course_id):
            raise ValidationFailedError("A platform FAQ entry has no organization or course.", code="INVALID_SCOPE")
        if scope == FaqScope.ORGANIZATION and not organization_id:
            raise ValidationFailedError("An organization FAQ entry needs an organization.", code="INVALID_SCOPE")
        if scope == FaqScope.COURSE and not course_id:
            raise ValidationFailedError("A course FAQ entry needs a course.", code="INVALID_SCOPE")

    async def create(
        self, auth: AccessTokenClaims, *, scope: str, organization_id: int | None, course_id: int | None, question: str, answer: str,
        source_message_id: int | None = None, citations: list[dict[str, object]] | None = None,
    ) -> FaqEntry:
        self._check_scope(scope, organization_id, course_id)
        self.authorize(auth, scope, organization_id)
        entry = FaqEntry(
            public_id=new_public_id(), scope=scope, organization_id=organization_id, course_id=course_id, question=question, answer=answer,
            status=FaqStatus.DRAFT, source_message_id=source_message_id, created_by=auth.user_id, citations=citations,
        )
        self.db.add(entry)
        await self.db.commit()
        return entry

    async def update(self, entry: FaqEntry, *, question: str | None, answer: str | None) -> FaqEntry:
        if entry.status == FaqStatus.ARCHIVED:
            raise ConflictError("An archived entry cannot be edited.", code="FAQ_ARCHIVED")
        changed = (question is not None and question != entry.question) or (answer is not None and answer != entry.answer)
        entry.question, entry.answer = question or entry.question, answer or entry.answer
        if changed:
            entry.embedding, entry.embedding_model = None, None
            if entry.status == FaqStatus.PUBLISHED:
                await self._embed(entry)
        await self.db.commit()
        return entry

    async def _embed(self, entry: FaqEntry) -> None:
        await self.db.commit()  # no transaction across the embedding call
        try:
            result = await self.gateway.embed(organization_id=entry.organization_id or self.settings.PLATFORM_ORGANIZATION_ID, user_id=None, texts=[entry.question])
        except GatewayError:
            return
        if result.vectors:
            entry.embedding, entry.embedding_model = result.vectors[0], result.model

    async def publish(self, entry: FaqEntry, *, by: int) -> FaqEntry:
        if entry.status == FaqStatus.ARCHIVED:
            raise ConflictError("An archived entry cannot be published.", code="FAQ_ARCHIVED")
        entry.status, entry.published_by = FaqStatus.PUBLISHED, by
        await self._embed(entry)
        await self.db.commit()
        return entry

    async def archive(self, entry: FaqEntry) -> FaqEntry:
        entry.status = FaqStatus.ARCHIVED
        await self.db.commit()
        return entry

    async def list_manageable(self, auth: AccessTokenClaims, *, status: str | None, scope: str | None, course_id: int | None, page: int, per_page: int) -> tuple[list[FaqEntry], int, bool]:
        stmt = select(FaqEntry).order_by(FaqEntry.created_at.desc(), FaqEntry.id)
        if status:
            stmt = stmt.where(FaqEntry.status == status)
        if scope:
            stmt = stmt.where(FaqEntry.scope == scope)
        if course_id:
            stmt = stmt.where(FaqEntry.course_id == course_id)
        visible: list[ColumnElement[bool]] = [FaqEntry.id.is_(None)]  # nothing, unless a rule below adds something
        if can_manage_support(auth):
            visible = [FaqEntry.id.is_not(None)]
        else:
            if can_author(auth):
                visible.append(FaqEntry.scope == FaqScope.COURSE)
            if is_institution_staff(auth):
                visible.append((FaqEntry.scope == FaqScope.ORGANIZATION) & (FaqEntry.organization_id == auth.organization_id))
        return await paginate(self.db, stmt.where(or_(*visible)), page, per_page)

    async def list_for_student(self, *, user_id: int, organization_id: int | None, course_id: int | None, q: str | None, limit: int = 20) -> list[FaqEntry]:
        courses = {course_id} if course_id else set()
        if not courses:
            rows = (
                await self.db.execute(
                    select(CourseVersionRef.course_id).join(EnrollmentRef, EnrollmentRef.version_id == CourseVersionRef.version_id).where(EnrollmentRef.student_user_id == user_id, EnrollmentRef.active.is_(True))
                )
            ).scalars()
            courses = set(rows)
        scope = FaqEntry.scope == FaqScope.PLATFORM
        if organization_id is not None:
            scope = or_(scope, (FaqEntry.scope == FaqScope.ORGANIZATION) & (FaqEntry.organization_id == organization_id))
        if courses:
            scope = or_(scope, (FaqEntry.scope == FaqScope.COURSE) & FaqEntry.course_id.in_(courses))
        entries = list((await self.db.execute(select(FaqEntry).where(FaqEntry.status == FaqStatus.PUBLISHED, scope).order_by(FaqEntry.helpful_count.desc(), FaqEntry.created_at))).scalars())
        if q and entries:
            scores = LexicalIndex([f"{e.question} {e.answer}" for e in entries]).scores(q)
            ranked = sorted(zip(entries, scores, strict=True), key=lambda pair: -float(pair[1]))
            entries = [e for e, score in ranked if score > 0]
        return entries[:limit]
