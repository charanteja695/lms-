"""Interview plans: drafted, published (and then never changed), versioned, retired.

A screening plan belongs to an employer and is used for its jobs' pipelines; a mock plan belongs to the platform and is offered to students for
practice. A published plan is immutable — an interview freezes the plan it was given, and the *same* plan and rubric are used for every candidate of
a job — so changing one means publishing a new version.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.conduct.plan_rules import PlanError, normalise
from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import Difficulty, PlanKind, PlanStatus
from app.models.plan import InterviewPlan
from app.permissions.policy import can_manage_careers, is_employer_member, owns_employer
from app.services.outbox import write_event


def _iso(value: Any) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


class PlanService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    # ------------------------------------------------------------------ lookup and access
    async def get(self, public_id: int) -> InterviewPlan:
        plan = (await self.db.execute(select(InterviewPlan).where(InterviewPlan.public_id == public_id))).scalar_one_or_none()
        if plan is None:
            raise NotFoundError("Interview plan not found.", code="PLAN_NOT_FOUND")
        return plan

    async def get_managed(self, auth: AccessTokenClaims, public_id: int) -> InterviewPlan:
        """A plan the caller may edit or read in full: their own company's (a careers manager: any). Someone else's is a 404."""
        plan = await self.get(public_id)
        if not owns_employer(auth, plan.owner_org_id) and not (plan.owner_org_id is None and can_manage_careers(auth)):
            raise NotFoundError("Interview plan not found.", code="PLAN_NOT_FOUND")
        return plan

    async def get_for_student(self, public_id: int) -> InterviewPlan:
        plan = await self.get(public_id)
        if plan.kind != PlanKind.MOCK or plan.status != PlanStatus.PUBLISHED:
            raise NotFoundError("Interview plan not found.", code="PLAN_NOT_FOUND")
        return plan

    # ------------------------------------------------------------------ writing
    @staticmethod
    def _rules(kind: PlanKind, difficulty: Difficulty, duration: int, rounds: list[dict[str, Any]], weights: dict[str, float] | None) -> tuple[list[dict[str, Any]], dict[str, float]]:
        try:
            return normalise(kind=kind, difficulty=difficulty, duration_minutes=duration, rounds=rounds, criteria_weights=weights)
        except PlanError as exc:
            raise ValidationFailedError(details=[{"field": exc.field, "code": exc.code, "message": exc.message}]) from exc

    def _check_owner(self, auth: AccessTokenClaims, kind: PlanKind) -> int | None:
        if kind == PlanKind.SCREENING:
            if not is_employer_member(auth):
                raise PermissionDeniedError("Only a company's recruiters and admins write screening plans.", code="EMPLOYERS_ONLY")
            return auth.organization_id
        if not can_manage_careers(auth):
            raise PermissionDeniedError("Only platform careers managers write mock-interview plans.", code="PERMISSION_DENIED")
        return None

    async def create(self, auth: AccessTokenClaims, fields: dict[str, Any]) -> InterviewPlan:
        kind, difficulty = PlanKind(fields["kind"]), Difficulty(fields["difficulty"])
        owner = self._check_owner(auth, kind)
        rounds, weights = self._rules(kind, difficulty, fields["duration_minutes"], fields["rounds"], fields.get("criteria_weights"))
        if kind == PlanKind.MOCK and fields.get("proctoring_level", "none") != "none":
            raise ValidationFailedError(details=[{"field": "proctoring_level", "code": "SCREENING_ONLY", "message": "Proctoring applies to screening interviews"}])
        family = new_public_id()
        plan = InterviewPlan(
            public_id=family, family_id=family, version=1, owner_org_id=owner, kind=kind, title=fields["title"], role=fields["role"], skills=fields.get("skills") or [], difficulty=difficulty,
            duration_minutes=fields["duration_minutes"], rounds=rounds, criteria_weights=weights, instructions=fields.get("instructions"), proctoring_level=fields.get("proctoring_level", "none"),
            max_attempts=fields.get("max_attempts", 1), retake_cooldown_days=fields.get("retake_cooldown_days", 30), status=PlanStatus.DRAFT, created_by=auth.user_id,
        )
        self.db.add(plan)
        await self.db.commit()
        return plan

    async def update(self, plan: InterviewPlan, fields: dict[str, Any]) -> InterviewPlan:
        plan = await self._locked(plan)
        if plan.status != PlanStatus.DRAFT:
            raise ConflictError("A published plan never changes: make a new version.", code="PLAN_NOT_DRAFT")
        for name in ("title", "role", "skills", "duration_minutes", "instructions", "proctoring_level", "max_attempts", "retake_cooldown_days"):
            if name in fields:
                setattr(plan, name, fields[name])
        if "difficulty" in fields:
            plan.difficulty = Difficulty(fields["difficulty"])
        if "rounds" in fields or "criteria_weights" in fields or "difficulty" in fields or "duration_minutes" in fields:
            raw = fields.get("rounds") or plan.rounds
            weights = fields.get("criteria_weights")
            plan.rounds, plan.criteria_weights = self._rules(PlanKind(plan.kind), Difficulty(plan.difficulty), plan.duration_minutes, raw, weights)
        if plan.kind == PlanKind.MOCK and plan.proctoring_level != "none":
            raise ValidationFailedError(details=[{"field": "proctoring_level", "code": "SCREENING_ONLY", "message": "Proctoring applies to screening interviews"}])
        await self.db.commit()
        return plan

    async def _locked(self, plan: InterviewPlan) -> InterviewPlan:
        return (await self.db.execute(select(InterviewPlan).where(InterviewPlan.id == plan.id).with_for_update().execution_options(populate_existing=True))).scalar_one()

    async def publish(self, plan: InterviewPlan) -> InterviewPlan:
        plan = await self._locked(plan)
        if plan.status != PlanStatus.DRAFT:
            raise ConflictError("Only a draft can be published.", code="PLAN_NOT_DRAFT")
        plan.status, plan.published_at = PlanStatus.PUBLISHED, utcnow()
        # a new version replaces the previous one for new interviews; interviews already created keep the plan they froze
        for older in (await self.db.execute(select(InterviewPlan).where(InterviewPlan.family_id == plan.family_id, InterviewPlan.id != plan.id, InterviewPlan.status == PlanStatus.PUBLISHED))).scalars():
            older.status = PlanStatus.RETIRED
        write_event(
            self.db, event_type="interview_plan.published", aggregate_type="interview_plan", aggregate_id=plan.id,
            payload={"plan_id": str(plan.public_id), "family_id": str(plan.family_id), "version": plan.version, "kind": plan.kind, "owner_org_id": str(plan.owner_org_id) if plan.owner_org_id else None, "occurred_at": _iso(utcnow())},
        )
        await self.db.commit()
        return plan

    async def retire(self, plan: InterviewPlan) -> InterviewPlan:
        plan = await self._locked(plan)
        if plan.status == PlanStatus.DRAFT:
            raise ConflictError("A draft is deleted by not publishing it; retire a published plan.", code="PLAN_NOT_PUBLISHED")
        plan.status = PlanStatus.RETIRED
        await self.db.commit()
        return plan

    async def new_version(self, auth: AccessTokenClaims, plan: InterviewPlan) -> InterviewPlan:
        """A draft copy of a published or retired plan, one version higher, for editing."""
        if plan.status == PlanStatus.DRAFT:
            raise ConflictError("This plan is already a draft.", code="PLAN_IS_DRAFT")
        newest = int((await self.db.execute(select(func.max(InterviewPlan.version)).where(InterviewPlan.family_id == plan.family_id))).scalar_one())
        drafts = int((await self.db.execute(select(func.count()).select_from(InterviewPlan).where(InterviewPlan.family_id == plan.family_id, InterviewPlan.status == PlanStatus.DRAFT))).scalar_one())
        if drafts:
            raise ConflictError("There is already a draft of this plan: finish or publish it.", code="DRAFT_EXISTS")
        draft = InterviewPlan(
            public_id=new_public_id(), family_id=plan.family_id, version=newest + 1, owner_org_id=plan.owner_org_id, kind=plan.kind, title=plan.title, role=plan.role, skills=list(plan.skills or []),
            difficulty=plan.difficulty, duration_minutes=plan.duration_minutes, rounds=[dict(r) for r in plan.rounds], criteria_weights=dict(plan.criteria_weights), instructions=plan.instructions,
            proctoring_level=plan.proctoring_level, max_attempts=plan.max_attempts, retake_cooldown_days=plan.retake_cooldown_days, status=PlanStatus.DRAFT, created_by=auth.user_id,
        )
        self.db.add(draft)
        await self.db.commit()
        return draft

    # ------------------------------------------------------------------ listing
    async def list_managed(self, auth: AccessTokenClaims, *, kind: str | None, status: str | None, page: int, per_page: int) -> tuple[list[InterviewPlan], int]:
        stmt = select(InterviewPlan)
        if not can_manage_careers(auth):
            stmt = stmt.where(InterviewPlan.owner_org_id == auth.organization_id)
        if kind:
            stmt = stmt.where(InterviewPlan.kind == kind)
        if status:
            stmt = stmt.where(InterviewPlan.status == status)
        total = int((await self.db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one())
        rows = (await self.db.execute(stmt.order_by(InterviewPlan.created_at.desc(), InterviewPlan.id).limit(per_page).offset((page - 1) * per_page))).scalars()
        return list(rows), total

    async def list_mock_for_students(self, *, page: int, per_page: int) -> tuple[list[InterviewPlan], int]:
        stmt = select(InterviewPlan).where(InterviewPlan.kind == PlanKind.MOCK, InterviewPlan.status == PlanStatus.PUBLISHED)
        total = int((await self.db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one())
        rows = (await self.db.execute(stmt.order_by(InterviewPlan.role, InterviewPlan.id).limit(per_page).offset((page - 1) * per_page))).scalars()
        return list(rows), total
