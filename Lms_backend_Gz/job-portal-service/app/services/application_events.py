"""What events and the worker do to applications: a hiring-test result completes the assessment stage, an interview report completes the
interview stage, and the assessment invitation is delivered to assessment-service. None of these can reject (the state machine forbids it)."""

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.assessment import AssessmentClient
from app.clients.errors import Rejected, Unavailable
from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.core.time import utcnow
from app.domain.enums import Actor, ApplicationStatus
from app.models.application import Application, ApplicationStage
from app.models.refs import HiringResult
from app.services.application_service import ApplicationService
from app.services.outbox import write_event

S = ApplicationStatus


def _int(value: Any) -> int | None:
    try:
        return int(str(value)) if value not in (None, "") else None
    except ValueError:
        return None


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class ApplicationEvents:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.applications = ApplicationService(db, settings)

    # ------------------------------------------------------------------ the hiring test
    async def assessment_result(self, payload: dict[str, Any]) -> None:
        """``attempt.finalized`` for a hiring test. Records the result on the candidate's application for that test and, the first time, completes the
        assessment stage. A later, higher ``revision`` (an integrity decision changed the result) updates the result and is noted in the history; it
        never moves the application backwards or rejects it — the recruiter sees the change and decides."""
        attempt_id, user_id, test_id = _int(payload.get("attempt_id")), _int(payload.get("user_id")), _int(payload.get("test_id"))
        if attempt_id is None or user_id is None or test_id is None:
            return
        revision = int(payload.get("revision") or 0)
        result = str(payload.get("result") or "failed")
        row = (await self.db.execute(select(HiringResult).where(HiringResult.attempt_id == attempt_id))).scalar_one_or_none()
        if row is not None and revision < row.revision:
            return
        if row is None:
            row = HiringResult(attempt_id=attempt_id, user_id=user_id, test_id=test_id, result=result, revision=revision)
            self.db.add(row)
        row.percent, row.result, row.integrity_status, row.revision = _float(payload.get("percent")), result, payload.get("integrity_status"), revision
        await self.db.flush()
        application = (
            await self.db.execute(
                select(Application).where(
                    Application.user_id == user_id, Application.assessment_test_id == test_id,
                    Application.status.in_([S.ASSESSMENT_INVITED, S.ASSESSMENT_COMPLETED, S.AI_INTERVIEW_INVITED, S.AI_INTERVIEW_COMPLETED, S.RECRUITER_REVIEW, S.HR_INTERVIEW, S.OFFERED]),
                )
            )
        ).scalar_one_or_none()
        if application is None:
            return  # a candidate who took a hiring test outside any application in flight
        application = await self.applications._locked(application)
        if revision < application.assessment_revision:
            return
        changed = application.assessment_result is not None and (application.assessment_result != row.result or application.assessment_integrity != row.integrity_status)
        application.assessment_percent, application.assessment_result = row.percent, row.result
        application.assessment_integrity, application.assessment_attempt_id, application.assessment_revision = row.integrity_status, attempt_id, revision
        if application.status == S.ASSESSMENT_INVITED:
            await self.applications.move(application, S.ASSESSMENT_COMPLETED, Actor.SYSTEM, actor_user_id=None, note=f"Assessment {row.result}" + (f" ({row.percent:g}%)" if row.percent is not None else ""), locked=True)
        elif changed:
            self.db.add(
                ApplicationStage(
                    application_id=application.id, from_status=application.status, to_status=application.status, actor=Actor.SYSTEM,
                    note=f"Assessment result revised: {row.result}" + (f", integrity {row.integrity_status}" if row.integrity_status else ""),
                )
            )
            job = await self.applications.job_of(application)
            write_event(
                self.db, event_type="application.assessment_revised", aggregate_type="application", aggregate_id=application.id,
                payload={
                    "application_id": str(application.public_id), "job_id": str(job.public_id), "employer_id": str(job.employer_org_id), "result": row.result,
                    "integrity_status": row.integrity_status, "occurred_at": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

    # ------------------------------------------------------------------ the AI interview (phase 10: contract only)
    async def interview_completed(self, payload: dict[str, Any]) -> None:
        """``interview.completed`` {application_id, interview_id, recommendation: strong_yes|yes|lean_no|no, score, report}. Completes the interview stage;
        the recommendation is shown to the recruiter, who decides (docs/PRODUCT.md §5.8: "human decision required")."""
        application_id = _int(payload.get("application_id"))
        if application_id is None:
            return
        try:
            application = await self.applications.get(application_id)
        except NotFoundError:
            return  # not one of ours
        if application.status != S.AI_INTERVIEW_INVITED:
            return
        application = await self.applications._locked(application)
        recommendation = str(payload.get("recommendation") or "")
        application.interview_recommendation = recommendation if recommendation in {"strong_yes", "yes", "lean_no", "no"} else None
        application.interview_score = _float(payload.get("score"))
        report = payload.get("report")
        application.interview_report = report if isinstance(report, dict) else None
        await self.applications.move(application, S.AI_INTERVIEW_COMPLETED, Actor.SYSTEM, actor_user_id=None, note=f"AI interview: {recommendation or 'completed'}", locked=True)

    # ------------------------------------------------------------------ delivering the assessment invitation
    async def deliver_assessment_invite(self, application_public_id: int, client: AssessmentClient) -> None:
        """Invite the candidate to the job's hiring test. Safe to repeat: assessment-service creates or updates the invitation. A refusal that can never
        succeed (unknown or unpublished test) marks the invitation ``failed`` so the recruiter sees it; a timeout is raised for the worker to retry."""
        application = await self.applications.get(application_public_id)
        if application.status != S.ASSESSMENT_INVITED or application.assessment_test_id is None:
            return
        if application.assessment_invite_state == "sent":
            return
        opens = utcnow()
        test_id, user_id, reference = application.assessment_test_id, application.user_id, str(application.public_id)
        await self.db.commit()
        try:
            await client.invite(
                test_id=test_id, user_id=user_id, reference=reference, opens_at=opens, expires_at=opens + timedelta(days=self.settings.ASSESSMENT_INVITE_VALID_DAYS), max_attempts=1
            )
        except Rejected as exc:
            application = await self.applications._locked(await self.applications.get(application_public_id))
            application.assessment_invite_state = "failed"
            self.db.add(ApplicationStage(application_id=application.id, from_status=application.status, to_status=application.status, actor=Actor.SYSTEM, note=f"Assessment invitation refused ({exc.code or exc.status})"))
            await self.db.commit()
            return
        except Unavailable:
            raise
        application = await self.applications._locked(await self.applications.get(application_public_id))
        application.assessment_invite_state = "sent"
        await self.db.commit()
