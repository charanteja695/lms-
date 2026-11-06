"""Calibration against human-rated samples, and the fairness audit of a plan (docs/PRODUCT.md §5.8 "Fairness")."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.errors import Unavailable
from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.domain.enums import Criterion, InterviewStatus, PlanKind, PlanStatus
from app.evaluation import audit
from app.models.calibration import CalibrationRun, CalibrationSample
from app.models.interview import Evaluation, Interview
from app.models.plan import InterviewPlan
from app.models.refs import OrgRef
from app.permissions.policy import can_manage_careers, owns_employer
from app.services.evaluation_service import EvaluationService


class AuditService:
    def __init__(self, db: AsyncSession, settings: Settings, evaluations: EvaluationService | None = None) -> None:
        self.db = db
        self.settings = settings
        self.evaluations = evaluations

    async def _current_plan(self, auth: AccessTokenClaims, plan_public_id: int) -> InterviewPlan:
        """The newest version of a plan's family that the caller may audit."""
        plan = (await self.db.execute(select(InterviewPlan).where(InterviewPlan.public_id == plan_public_id))).scalar_one_or_none()
        if plan is None or not (can_manage_careers(auth) or owns_employer(auth, plan.owner_org_id)):
            raise NotFoundError("Interview plan not found.", code="PLAN_NOT_FOUND")
        newest = (
            await self.db.execute(select(InterviewPlan).where(InterviewPlan.family_id == plan.family_id, InterviewPlan.status != PlanStatus.DRAFT).order_by(InterviewPlan.version.desc()).limit(1))
        ).scalar_one_or_none()
        return newest or plan

    # ------------------------------------------------------------------ calibration
    async def add_sample(self, auth: AccessTokenClaims, plan_public_id: int, *, turns: list[dict[str, Any]], scores: dict[str, float], recommendation: str) -> CalibrationSample:
        plan = await self._current_plan(auth, plan_public_id)
        known = {c.value for c in Criterion}
        if not set(scores) <= known or not scores or any(not 1 <= v <= 5 for v in scores.values()):
            raise ValidationFailedError(details=[{"field": "human_scores", "code": "INVALID_SCORES", "message": "Score known criteria from 1 to 5"}])
        used = {c for r in plan.rounds for c in r["criteria"]}
        if not set(scores) <= used:
            raise ValidationFailedError(details=[{"field": "human_scores", "code": "UNKNOWN_CRITERION", "message": "This plan does not score: " + ", ".join(sorted(set(scores) - used))}])
        sample = CalibrationSample(public_id=new_public_id(), plan_family_id=plan.family_id, turns=turns, human_scores=scores, human_recommendation=recommendation, rated_by=auth.user_id)
        self.db.add(sample)
        await self.db.commit()
        return sample

    async def samples(self, auth: AccessTokenClaims, plan_public_id: int) -> list[CalibrationSample]:
        plan = await self._current_plan(auth, plan_public_id)
        return list((await self.db.execute(select(CalibrationSample).where(CalibrationSample.plan_family_id == plan.family_id).order_by(CalibrationSample.created_at))).scalars())

    async def run_calibration(self, auth: AccessTokenClaims, plan_public_id: int) -> CalibrationRun:
        """Score every rated sample with the current prompt and plan and compare with the people's scores."""
        if self.evaluations is None:
            raise ConflictError("Calibration needs the AI evaluator.", code="EVALUATOR_UNAVAILABLE")
        plan = await self._current_plan(auth, plan_public_id)
        samples = list((await self.db.execute(select(CalibrationSample).where(CalibrationSample.plan_family_id == plan.family_id).order_by(CalibrationSample.created_at).limit(self.settings.CALIBRATION_MAX_SAMPLES))).scalars())
        if not samples:
            raise ConflictError("Add human-rated samples first.", code="NO_SAMPLES")
        snapshot = {"role": plan.role, "difficulty": plan.difficulty, "rounds": plan.rounds, "criteria_weights": plan.criteria_weights}
        billing = plan.owner_org_id or self.settings.PLATFORM_ORGANIZATION_ID
        await self.db.commit()
        pairs, details, model, version = [], [], None, None
        for sample in samples:
            try:
                result, call, _ = await self.evaluations.score_transcript(snapshot, sample.turns, billing_org=billing)
            except Unavailable as exc:
                raise ConflictError(f"The evaluator could not score every sample: {exc}", code="EVALUATOR_UNAVAILABLE") from exc
            model, version = call.model, call.prompt_version
            pairs.append((sample.human_scores, result.criterion_scores, sample.human_recommendation, result.recommendation))
            details.append({"sample_id": str(sample.public_id), "human": sample.human_scores, "ai": result.criterion_scores, "human_recommendation": sample.human_recommendation, "ai_recommendation": result.recommendation})
        metrics = audit.calibration(pairs)
        run = CalibrationRun(
            public_id=new_public_id(), plan_family_id=plan.family_id, prompt_version=version, model=model, samples=int(metrics["samples"] or 0), mean_abs_error=metrics["mean_abs_error"],
            within_one_rate=metrics["within_one_rate"], recommendation_agreement=metrics["recommendation_agreement"], details=details, run_by=auth.user_id,
        )
        self.db.add(run)
        await self.db.commit()
        return run

    async def runs(self, auth: AccessTokenClaims, plan_public_id: int) -> list[CalibrationRun]:
        plan = await self._current_plan(auth, plan_public_id)
        return list((await self.db.execute(select(CalibrationRun).where(CalibrationRun.plan_family_id == plan.family_id).order_by(CalibrationRun.created_at.desc()).limit(20))).scalars())

    # ------------------------------------------------------------------ the fairness audit
    async def report(self, auth: AccessTokenClaims, plan_public_id: int) -> dict[str, Any]:
        """Outcomes of every screening interview of a plan (all versions): recommendation mix, how often people overrode the AI, evidence quality, the
        four-fifths comparison across the candidates' institutions, and the latest calibration."""
        plan = await self._current_plan(auth, plan_public_id)
        if plan.kind != PlanKind.SCREENING:
            raise ConflictError("The fairness audit covers hiring interviews.", code="NOT_SCREENING")
        family_plan_ids = list((await self.db.execute(select(InterviewPlan.public_id).where(InterviewPlan.family_id == plan.family_id))).scalars())
        rows = (
            await self.db.execute(
                select(Interview, Evaluation).join(Evaluation, Evaluation.interview_id == Interview.id).where(Interview.plan_id.in_(family_plan_ids), Interview.status.in_([InterviewStatus.EVALUATED, InterviewStatus.REVIEWED]))
            )
        ).all()
        mix: dict[str, int] = {}
        groups: dict[str, list[int]] = {}
        overrides = reviewed = quotes = invalid = 0
        scores: list[float] = []
        for interview, evaluation in rows:
            final = interview.final_recommendation or evaluation.recommendation
            mix[final or "none"] = mix.get(final or "none", 0) + 1
            if evaluation.overall_score is not None:
                scores.append(evaluation.overall_score)
            quotes, invalid = quotes + evaluation.total_quotes, invalid + evaluation.invalid_quotes
            if interview.status == InterviewStatus.REVIEWED:
                reviewed += 1
                overrides += int(interview.final_recommendation != evaluation.recommendation)
            label = str(interview.organization_id) if interview.organization_id else "none"
            bucket = groups.setdefault(label, [0, 0])
            bucket[0] += 1
            bucket[1] += int(final in audit.ADVANCE)
        names = {org.org_id: org.name for org in (await self.db.execute(select(OrgRef).where(OrgRef.org_id.in_([int(k) for k in groups if k != "none"])))).scalars()} if groups else {}
        impact = audit.adverse_impact({names.get(int(k), k) if k != "none" else "no institution": (v[0], v[1]) for k, v in groups.items()}, min_group=self.settings.AUDIT_MIN_GROUP)
        latest = (await self.db.execute(select(CalibrationRun).where(CalibrationRun.plan_family_id == plan.family_id).order_by(CalibrationRun.created_at.desc()).limit(1))).scalar_one_or_none()
        total = int((await self.db.execute(select(func.count()).select_from(Interview).where(Interview.plan_id.in_(family_plan_ids)))).scalar_one())
        return {
            "plan_id": str(plan.public_id), "family_id": str(plan.family_id), "interviews": total, "evaluated": len(rows), "recommendations": mix,
            "average_score": round(sum(scores) / len(scores), 2) if scores else None, "reviewed": reviewed, "override_rate": round(overrides / reviewed, 3) if reviewed else None,
            "invalid_quote_rate": round(invalid / quotes, 3) if quotes else None, "adverse_impact": impact,
            "calibration": {"run_id": str(latest.public_id), "mean_abs_error": latest.mean_abs_error, "within_one_rate": latest.within_one_rate, "recommendation_agreement": latest.recommendation_agreement,
                            "samples": latest.samples, "prompt_version": latest.prompt_version, "at": latest.created_at.strftime("%Y-%m-%dT%H:%M:%SZ")} if latest else None,
            "note": "Groups are the candidates' institutions, the only attribute this service holds. It is a screen for human review, not a verdict.",
        }
