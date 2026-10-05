"""The human side of a screening interview: a person confirms or overrides the AI's recommendation (docs/PRODUCT.md §5.8 "Human decision required in
hiring"), the candidate reads their feedback, and may appeal; a second person decides the appeal, and an upheld appeal grants a retake.
"""

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, PermissionDeniedError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import AppealStatus, InterviewStatus, PlanKind
from app.models.interview import Appeal, Evaluation, Interview
from app.permissions.policy import can_manage_careers
from app.services.interview_service import InterviewService
from app.services.outbox import write_event


class ReviewService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.interviews = InterviewService(db, settings)

    async def evaluation(self, interview: Interview) -> Evaluation | None:
        return (await self.db.execute(select(Evaluation).where(Evaluation.interview_id == interview.id))).scalar_one_or_none()

    def _event(self, event_type: str, interview: Interview, **extra: Any) -> None:
        write_event(
            self.db, event_type=event_type, aggregate_type="interview", aggregate_id=interview.id,
            payload={
                "interview_id": str(interview.public_id), "application_id": str(interview.application_id) if interview.application_id else None, "user_id": str(interview.user_id),
                "employer_id": str(interview.employer_org_id) if interview.employer_org_id else None, "occurred_at": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), **extra,
            },
        )

    # ------------------------------------------------------------------ the recruiter's review
    async def review(self, auth: AccessTokenClaims, interview: Interview, *, recommendation: str | None, note: str | None, release_feedback: bool) -> Interview:
        """Confirm the AI's recommendation (send none) or override it (send one, with a note saying why). Releases the candidate's feedback if asked."""
        interview = await self.interviews.locked(interview)
        if interview.kind != PlanKind.SCREENING:
            raise ConflictError("Only hiring interviews are reviewed.", code="NOT_SCREENING")
        if interview.status not in {InterviewStatus.EVALUATED, InterviewStatus.REVIEWED}:
            raise ConflictError("The interview has not been evaluated yet.", code="NOT_EVALUATED")
        evaluation = await self.evaluation(interview)
        if evaluation is None:
            raise ConflictError("The interview has not been evaluated yet.", code="NOT_EVALUATED")
        ai = evaluation.recommendation
        final = recommendation or ai
        if final is None:
            raise ValidationFailedError(details=[{"field": "recommendation", "code": "REQUIRED", "message": "There is no AI recommendation to confirm: give your own"}])
        if recommendation is not None and recommendation != ai and not note:
            raise ValidationFailedError(details=[{"field": "note", "code": "REQUIRED", "message": "Say why you are overriding the recommendation"}])
        interview.status, interview.reviewed_by, interview.reviewed_at = InterviewStatus.REVIEWED, auth.user_id, utcnow()
        interview.final_recommendation, interview.review_note = final, note
        if release_feedback:
            interview.feedback_released = True
        self._event("interview.reviewed", interview, ai_recommendation=ai, final_recommendation=final, overridden=final != ai, feedback_released=interview.feedback_released)
        await self.db.commit()
        return interview

    # ------------------------------------------------------------------ appeals
    async def appeal(self, user_id: int, interview: Interview, reason: str) -> Appeal:
        interview = await self.interviews.locked(interview)
        if interview.user_id != user_id or interview.kind != PlanKind.SCREENING:
            raise PermissionDeniedError("Only the candidate of a hiring interview can appeal it.", code="NOT_YOURS")
        if not interview.feedback_released or interview.status not in {InterviewStatus.EVALUATED, InterviewStatus.REVIEWED}:
            raise ConflictError("You can appeal once your feedback has been released.", code="NOT_RELEASED")
        since = interview.reviewed_at or interview.completed_at or utcnow()
        if utcnow() > since + timedelta(days=self.settings.APPEAL_WINDOW_DAYS):
            raise ConflictError(f"Appeals must be made within {self.settings.APPEAL_WINDOW_DAYS} days.", code="APPEAL_WINDOW_PASSED")
        existing = (await self.db.execute(select(Appeal).where(Appeal.interview_id == interview.id))).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("You have already appealed this interview.", code="ALREADY_APPEALED")
        appeal = Appeal(public_id=new_public_id(), interview_id=interview.id, user_id=user_id, reason=reason, status=AppealStatus.OPEN)
        self.db.add(appeal)
        await self.db.flush()
        self._event("interview.appealed", interview, appeal_id=str(appeal.public_id))
        await self.db.commit()
        return appeal

    async def get_appeal(self, interview: Interview) -> Appeal | None:
        return (await self.db.execute(select(Appeal).where(Appeal.interview_id == interview.id))).scalar_one_or_none()

    async def decide(self, auth: AccessTokenClaims, interview: Interview, *, uphold: bool, note: str | None) -> Appeal:
        """A person other than the one who reviewed the interview decides an appeal (a careers manager may always). Upheld: the candidate may retake."""
        interview = await self.interviews.locked(interview)
        appeal = await self.get_appeal(interview)
        if appeal is None or appeal.status != AppealStatus.OPEN:
            raise ConflictError("There is no open appeal on this interview.", code="NO_OPEN_APPEAL")
        if interview.reviewed_by == auth.user_id and not can_manage_careers(auth):
            raise PermissionDeniedError("The person who reviewed the interview cannot decide its appeal.", code="SECOND_REVIEWER_REQUIRED")
        if not uphold and not note:
            raise ValidationFailedError(details=[{"field": "note", "code": "REQUIRED", "message": "Say why the appeal is denied: the candidate reads it"}])
        appeal.status, appeal.decided_by, appeal.decided_at, appeal.decision_note = (AppealStatus.UPHELD if uphold else AppealStatus.DENIED), auth.user_id, utcnow(), note
        if uphold:
            interview.retake_granted = True
        self._event("interview.appeal_decided", interview, appeal_id=str(appeal.public_id), decision=appeal.status, retake_granted=interview.retake_granted)
        await self.db.commit()
        return appeal

    async def open_appeals(self, auth: AccessTokenClaims, *, page: int, per_page: int) -> tuple[list[tuple[Appeal, Interview]], int]:
        stmt = select(Appeal, Interview).join(Interview, Interview.id == Appeal.interview_id).where(Appeal.status == AppealStatus.OPEN)
        if not can_manage_careers(auth):
            stmt = stmt.where(Interview.employer_org_id == auth.organization_id)
        total = int((await self.db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one())
        rows = (await self.db.execute(stmt.order_by(Appeal.created_at).limit(per_page).offset((page - 1) * per_page))).all()
        return [(a, i) for a, i in rows], total

