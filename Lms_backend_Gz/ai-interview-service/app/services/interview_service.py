"""The life of an interview: invited → (consent) → in progress → completed → evaluated → reviewed, or expired / cancelled.

Every change takes a row lock on the interview first. The clock is the server's: ``ends_at`` is set when the interview starts and nothing a client
sends moves it. A candidate can have several interviews (mock practice, and screening interviews the hiring pipeline has sent them), each frozen to
the plan it was created from.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.conduct import director
from app.conduct.plan_rules import total_seconds
from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, RateLimitedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import InterviewStatus, PlanKind, PlanStatus, Speaker, TurnKind, WorkKind
from app.models.interview import Interview, InterviewTurn
from app.models.plan import InterviewPlan
from app.permissions.policy import can_manage_careers, owns_employer
from app.services import work_service
from app.services.outbox import write_event

CONSENT_VERSION = "2026-09"
CONSENT_TEXT = (
    "This is an AI-led interview. Your answers are turned into a transcript that is scored against a fixed rubric and, for a hiring interview, read by a recruiter, who makes "
    "the decision. If you allow recording, your audio is kept for the same purpose. You can stop at any time; stopping early ends the interview."
)


def _iso(value: Any) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


class InterviewService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    # ------------------------------------------------------------------ lookup
    async def get(self, public_id: int) -> Interview:
        interview = (await self.db.execute(select(Interview).where(Interview.public_id == public_id))).scalar_one_or_none()
        if interview is None:
            raise NotFoundError("Interview not found.", code="INTERVIEW_NOT_FOUND")
        return interview

    async def get_mine(self, user_id: int, public_id: int) -> Interview:
        interview = await self.get(public_id)
        if interview.user_id != user_id:
            raise NotFoundError("Interview not found.", code="INTERVIEW_NOT_FOUND")
        return interview

    async def get_for_employer(self, auth: AccessTokenClaims, public_id: int) -> Interview:
        interview = await self.get(public_id)
        if interview.kind != PlanKind.SCREENING or not owns_employer(auth, interview.employer_org_id):
            raise NotFoundError("Interview not found.", code="INTERVIEW_NOT_FOUND")
        return interview

    async def locked(self, interview: Interview) -> Interview:
        return (await self.db.execute(select(Interview).where(Interview.id == interview.id).with_for_update().execution_options(populate_existing=True))).scalar_one()

    async def turns(self, interview: Interview) -> list[InterviewTurn]:
        return list((await self.db.execute(select(InterviewTurn).where(InterviewTurn.interview_id == interview.id).order_by(InterviewTurn.seq))).scalars())

    def _event(self, event_type: str, interview: Interview, **extra: Any) -> None:
        write_event(
            self.db, event_type=event_type, aggregate_type="interview", aggregate_id=interview.id,
            payload={
                "interview_id": str(interview.public_id), "plan_id": str(interview.plan_id), "kind": interview.kind, "user_id": str(interview.user_id),
                "application_id": str(interview.application_id) if interview.application_id else None, "job_id": str(interview.job_id) if interview.job_id else None,
                "employer_id": str(interview.employer_org_id) if interview.employer_org_id else None, "status": interview.status, "occurred_at": _iso(utcnow()), **extra,
            },
        )

    def add_turn(
        self, interview: Interview, *, speaker: Speaker, kind: TurnKind, text: str, round_key: str, key: str | None = None, via: str = "text", meta: dict[str, Any] | None = None,
    ) -> InterviewTurn:
        """Append to the transcript. The caller holds the interview's lock, so ``turn_count`` hands out consecutive numbers."""
        interview.turn_count += 1
        elapsed = int((utcnow() - interview.started_at).total_seconds() * 1000) if interview.started_at else 0
        turn = InterviewTurn(interview_id=interview.id, seq=interview.turn_count, round_key=round_key, speaker=speaker, kind=kind, text=text, elapsed_ms=elapsed, idempotency_key=key, via=via, meta=meta)
        self.db.add(turn)
        return turn

    # ------------------------------------------------------------------ creating
    async def create_mock(self, auth: AccessTokenClaims, plan: InterviewPlan) -> Interview:
        """A student's practice interview, within their monthly allowance."""
        if plan.kind != PlanKind.MOCK or plan.status != PlanStatus.PUBLISHED:
            raise NotFoundError("Interview plan not found.", code="PLAN_NOT_FOUND")
        month_start = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        used = int(
            (
                await self.db.execute(
                    select(func.count()).select_from(Interview).where(
                        Interview.user_id == auth.user_id, Interview.kind == PlanKind.MOCK, Interview.created_at >= month_start, Interview.status != InterviewStatus.CANCELLED
                    )
                )
            ).scalar_one()
        )
        if used >= self.settings.MOCK_INTERVIEWS_PER_MONTH:
            raise RateLimitedError(retry_after=86_400, message=f"You have used your {self.settings.MOCK_INTERVIEWS_PER_MONTH} practice interviews for this month.", code="MOCK_QUOTA_EXCEEDED")
        open_ones = int(
            (
                await self.db.execute(
                    select(func.count()).select_from(Interview).where(Interview.user_id == auth.user_id, Interview.kind == PlanKind.MOCK, Interview.status.in_([InterviewStatus.INVITED, InterviewStatus.IN_PROGRESS]))
                )
            ).scalar_one()
        )
        if open_ones:
            raise ConflictError("Finish or end your open practice interview first.", code="INTERVIEW_ALREADY_OPEN")
        interview = self._new(plan, user_id=auth.user_id, organization_id=auth.organization_id, attempt_no=1, expires=utcnow() + timedelta(days=1))
        self.db.add(interview)
        await self.db.flush()
        self._event("interview.invited", interview)
        await self.db.commit()
        return interview

    def _new(self, plan: InterviewPlan, *, user_id: int, organization_id: int | None, attempt_no: int, expires: datetime, application: dict[str, int | None] | None = None) -> Interview:
        snapshot = {
            "plan_id": plan.public_id, "family_id": plan.family_id, "version": plan.version, "title": plan.title, "role": plan.role, "skills": list(plan.skills or []), "difficulty": plan.difficulty,
            "duration_minutes": plan.duration_minutes, "rounds": plan.rounds, "criteria_weights": plan.criteria_weights, "instructions": plan.instructions,
        }
        link = application or {}
        return Interview(
            public_id=new_public_id(), plan_id=plan.public_id, plan_snapshot=snapshot, user_id=user_id, organization_id=organization_id, kind=plan.kind, application_id=link.get("application_id"),
            job_id=link.get("job_id"), employer_org_id=link.get("employer_id") or plan.owner_org_id if plan.kind == PlanKind.SCREENING else None, attempt_no=attempt_no, status=InterviewStatus.INVITED,
            invite_expires_at=expires, proctoring_level=plan.proctoring_level, turn_count=0, round_index=0, question_index=0, follow_ups=0, code_runs=0, feedback_released=False, retake_granted=False,
        )

    async def create_screening(self, payload: dict[str, Any]) -> Interview | None:
        """Invite a candidate the hiring pipeline sent here (``application.stage_changed`` to ``ai_interview_invited``). Idempotent per application and attempt;
        the plan must be a published screening plan of the job's own employer. Returns None when there is nothing to do."""
        application_id, user_id, plan_id, employer_id = (int(payload[k]) if payload.get(k) else None for k in ("application_id", "user_id", "plan_id", "employer_id"))
        if application_id is None or user_id is None or plan_id is None or employer_id is None:
            return None
        plan = (await self.db.execute(select(InterviewPlan).where(InterviewPlan.public_id == plan_id))).scalar_one_or_none()
        if plan is None or plan.kind != PlanKind.SCREENING or plan.owner_org_id != employer_id:
            raise ConflictError("The job names an interview plan this company does not have.", code="PLAN_NOT_FOUND")
        if plan.status == PlanStatus.DRAFT:
            raise ConflictError("The job's interview plan is not published yet.", code="PLAN_NOT_PUBLISHED")
        # the newest published version of the plan's family is the one candidates get; every candidate of a job gets the same one until it is superseded
        current = (
            await self.db.execute(select(InterviewPlan).where(InterviewPlan.family_id == plan.family_id, InterviewPlan.status == PlanStatus.PUBLISHED).order_by(InterviewPlan.version.desc()).limit(1))
        ).scalar_one_or_none() or plan
        existing = int((await self.db.execute(select(func.count()).select_from(Interview).where(Interview.application_id == application_id))).scalar_one())
        if existing:
            return None
        interview = self._new(
            current, user_id=user_id, organization_id=int(payload["organization_id"]) if payload.get("organization_id") else None, attempt_no=1,
            expires=utcnow() + timedelta(days=self.settings.INVITE_VALID_DAYS), application={"application_id": application_id, "job_id": int(payload["job_id"]) if payload.get("job_id") else None, "employer_id": employer_id},
        )
        self.db.add(interview)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            return None
        self._event("interview.invited", interview, expires_at=_iso(interview.invite_expires_at))
        return interview

    async def cancel_for_application(self, application_id: int, reason: str) -> int:
        """The application ended (withdrawn, rejected, placed…): an interview nobody started is cancelled."""
        rows = list(
            (await self.db.execute(select(Interview).where(Interview.application_id == application_id, Interview.status == InterviewStatus.INVITED).with_for_update())).scalars()
        )
        for interview in rows:
            interview.status = InterviewStatus.CANCELLED
            self._event("interview.cancelled", interview, reason=reason)
        return len(rows)

    # ------------------------------------------------------------------ consent and start
    def consent_info(self, interview: Interview) -> dict[str, Any]:
        strict = interview.proctoring_level == "strict"
        return {"version": CONSENT_VERSION, "text": CONSENT_TEXT, "recording_required": strict, "instructions": interview.plan_snapshot.get("instructions")}

    async def consent(self, interview: Interview, *, version: str, recording: bool) -> Interview:
        interview = await self.locked(interview)
        await self._require_invited(interview)
        if version != CONSENT_VERSION:
            raise ConflictError("The consent text has changed: read it again.", code="CONSENT_VERSION_CHANGED")
        if interview.proctoring_level == "strict" and not recording:
            raise ConflictError("This interview is proctored: recording must be allowed to take it.", code="RECORDING_REQUIRED")
        interview.consent = {"version": version, "accepted_at": _iso(utcnow()), "recording": recording}
        await self.db.commit()
        return interview

    async def _require_invited(self, interview: Interview) -> None:
        if interview.status != InterviewStatus.INVITED:
            raise ConflictError(f"This interview is {interview.status}.", code="INVALID_STATE")
        if interview.invite_expires_at and interview.invite_expires_at < utcnow():
            interview.status = InterviewStatus.EXPIRED
            self._event("interview.expired", interview)
            await self.db.commit()
            raise ConflictError("This invitation has expired.", code="INVITATION_EXPIRED")

    async def start(self, interview: Interview) -> tuple[Interview, InterviewTurn]:
        interview = await self.locked(interview)
        await self._require_invited(interview)
        if not interview.consent:
            raise ConflictError("Read and accept the consent first.", code="CONSENT_REQUIRED")
        accepted = datetime.strptime(interview.consent["accepted_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=utcnow().tzinfo)
        if utcnow() - accepted > timedelta(minutes=self.settings.START_GRACE_MINUTES):
            interview.consent = None
            await self.db.commit()
            raise ConflictError("You took too long to start: please accept the consent again.", code="CONSENT_EXPIRED")
        if interview.kind == PlanKind.SCREENING and interview.integrity_status == "invalidated":
            raise ConflictError("This interview cannot be taken.", code="INVALID_STATE")
        plan = interview.plan_snapshot
        now = utcnow()
        interview.status, interview.started_at, interview.round_started_at = InterviewStatus.IN_PROGRESS, now, now
        interview.ends_at = now + timedelta(minutes=int(plan["duration_minutes"]))
        opening = self.add_turn(interview, speaker=Speaker.INTERVIEWER, kind=TurnKind.QUESTION, text=director.opening_text(plan), round_key=plan["rounds"][0]["key"])
        self._event("interview.started", interview, ends_at=_iso(interview.ends_at), proctoring_level=interview.proctoring_level)
        await self.db.commit()
        return interview, opening

    # ------------------------------------------------------------------ completing
    async def complete(self, interview: Interview, reason: str) -> Interview:
        """End the conversation. The interview is then waiting to be evaluated; the result is announced when the evaluation is done."""
        if interview.status != InterviewStatus.IN_PROGRESS:
            return interview
        interview.status, interview.completed_at, interview.complete_reason, interview.awaiting_reply_since = InterviewStatus.COMPLETED, utcnow(), reason, None
        await work_service.enqueue(self.db, WorkKind.EVALUATE, interview.public_id)
        self._event("interview.finished", interview, reason=reason)
        return interview

    async def end(self, interview: Interview) -> Interview:
        interview = await self.locked(interview)
        if interview.status != InterviewStatus.IN_PROGRESS:
            raise ConflictError(f"This interview is {interview.status}.", code="INVALID_STATE")
        if interview.turn_count:
            self.add_turn(interview, speaker=Speaker.SYSTEM, kind=TurnKind.NOTE, text="The candidate ended the interview.", round_key=self.current_round(interview)["key"])
        await self.complete(interview, "candidate_ended")
        await self.db.commit()
        return interview

    def current_round(self, interview: Interview) -> dict[str, Any]:
        rounds: list[dict[str, Any]] = interview.plan_snapshot["rounds"]
        return rounds[min(interview.round_index, len(rounds) - 1)]

    def seconds_left(self, interview: Interview) -> tuple[float, float]:
        """(seconds left in the current round, seconds left in the interview) by the server's clock."""
        now = utcnow()
        overall = (interview.ends_at - now).total_seconds() if interview.ends_at else 0.0
        started = interview.round_started_at or now
        round_left = total_seconds([self.current_round(interview)]) - (now - started).total_seconds()
        return round_left, overall

    async def close_stale(self, *, limit: int = 200) -> tuple[int, int]:
        """The worker's sweep: end interviews whose time ran out (and abandoned ones), expire invitations nobody used. Returns ``(completed, expired)``."""
        now = utcnow()
        grace = timedelta(seconds=self.settings.OVERRUN_GRACE_SECONDS)
        running = list(
            (
                await self.db.execute(
                    select(Interview).where(Interview.status == InterviewStatus.IN_PROGRESS, Interview.ends_at < now - grace).limit(limit).with_for_update(skip_locked=True)
                )
            ).scalars()
        )
        for interview in running:
            if interview.turn_count:
                self.add_turn(interview, speaker=Speaker.SYSTEM, kind=TurnKind.NOTE, text="The interview's time ran out.", round_key=self.current_round(interview)["key"])
            await self.complete(interview, "time_up")
        stale = list(
            (
                await self.db.execute(
                    select(Interview).where(Interview.status == InterviewStatus.INVITED, Interview.invite_expires_at < now).limit(limit).with_for_update(skip_locked=True)
                )
            ).scalars()
        )
        for interview in stale:
            interview.status = InterviewStatus.EXPIRED
            self._event("interview.expired", interview)
        await self.db.commit()
        return len(running), len(stale)

    # ------------------------------------------------------------------ retake
    async def retake(self, auth: AccessTokenClaims, interview: Interview) -> Interview:
        """A screening candidate whose appeal was upheld gets a fresh attempt at the same plan; a practice interview is simply started again."""
        interview = await self.locked(interview)
        if interview.user_id != auth.user_id:
            raise NotFoundError("Interview not found.", code="INTERVIEW_NOT_FOUND")
        if interview.kind != PlanKind.SCREENING or not interview.retake_granted:
            raise PermissionDeniedError("A retake has not been granted for this interview.", code="RETAKE_NOT_GRANTED")
        again = (await self.db.execute(select(func.count()).select_from(Interview).where(Interview.application_id == interview.application_id, Interview.attempt_no > interview.attempt_no))).scalar_one()
        if again:
            raise ConflictError("The retake has already been created.", code="RETAKE_EXISTS")
        plan = (await self.db.execute(select(InterviewPlan).where(InterviewPlan.public_id == interview.plan_id))).scalar_one()
        current = (
            await self.db.execute(select(InterviewPlan).where(InterviewPlan.family_id == plan.family_id, InterviewPlan.status == PlanStatus.PUBLISHED).order_by(InterviewPlan.version.desc()).limit(1))
        ).scalar_one_or_none() or plan
        fresh = self._new(
            current, user_id=interview.user_id, organization_id=interview.organization_id, attempt_no=interview.attempt_no + 1,
            expires=utcnow() + timedelta(days=self.settings.INVITE_VALID_DAYS), application={"application_id": interview.application_id, "job_id": interview.job_id, "employer_id": interview.employer_org_id},
        )
        self.db.add(fresh)
        await self.db.flush()
        self._event("interview.invited", fresh, retake_of=str(interview.public_id), expires_at=_iso(fresh.invite_expires_at))
        await self.db.commit()
        return fresh

    # ------------------------------------------------------------------ listing
    async def list_mine(self, user_id: int, *, status: str | None, kind: str | None, page: int, per_page: int) -> tuple[list[Interview], int]:
        stmt = select(Interview).where(Interview.user_id == user_id)
        if status:
            stmt = stmt.where(Interview.status == status)
        if kind:
            stmt = stmt.where(Interview.kind == kind)
        return await self._page(stmt.order_by(Interview.created_at.desc(), Interview.id), page, per_page)

    async def list_for_employer(
        self, auth: AccessTokenClaims, *, status: str | None, application_id: int | None, job_id: int | None, page: int, per_page: int
    ) -> tuple[list[Interview], int]:
        stmt = select(Interview).where(Interview.kind == PlanKind.SCREENING)
        if not can_manage_careers(auth):
            stmt = stmt.where(Interview.employer_org_id == auth.organization_id)
        if status:
            stmt = stmt.where(Interview.status == status)
        if application_id is not None:
            stmt = stmt.where(Interview.application_id == application_id)
        if job_id is not None:
            stmt = stmt.where(Interview.job_id == job_id)
        return await self._page(stmt.order_by(Interview.created_at.desc(), Interview.id), page, per_page)

    async def _page(self, stmt: Any, page: int, per_page: int) -> tuple[list[Interview], int]:
        total = int((await self.db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one())
        rows: Any = (await self.db.execute(stmt.limit(per_page).offset((page - 1) * per_page))).scalars()
        return list(rows), total
