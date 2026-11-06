"""Applications and the hiring pipeline (docs/PRODUCT.md §5.7).

Every move goes through ``move``, which locks the application, asks the state machine (app/pipeline/machine.py) whether *this actor* may
make *this move* under *this job's template*, writes the history row, and emits ``application.stage_changed`` in the same transaction.
Three things hold no matter who calls:

  * the system (the AI screening, an event handler) can never reject: only ``reject_batch`` rejects, and it needs a person's confirmation;
  * only the candidate withdraws or answers an offer;
  * an offer or a placement is made through its own method (offers, ``place``), never by naming the status.
"""

from datetime import datetime
from typing import Any

from lms_common.pagination import LIKE_ESCAPE, contains_pattern
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.career import CareerClient
from app.clients.errors import Rejected, Unavailable
from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import TERMINAL_STATUSES, Actor, ApplicationStatus, JobStatus, OfferStatus, WorkKind
from app.matching import eligibility
from app.models.application import Application, ApplicationNote, ApplicationStage, RejectionBatch
from app.models.employer import EmployerProfile
from app.models.job import Job
from app.models.offer import Offer
from app.models.refs import UserRef
from app.permissions.policy import owns_employer
from app.pipeline import machine
from app.services import work_service
from app.services.candidate_service import CandidateService, to_candidate, to_preferences
from app.services.job_service import JobService
from app.services.match_service import MatchService
from app.services.outbox import write_event

S = ApplicationStatus
# statuses a recruiter may name directly in a transition request: the rest are events, offers, placement or a confirmed rejection
_RECRUITER_TARGETS = {S.SHORTLISTED, S.ASSESSMENT_INVITED, S.AI_INTERVIEW_INVITED, S.RECRUITER_REVIEW, S.HR_INTERVIEW}


def _iso(value: Any) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


def template_of(job: Job) -> machine.Template:
    pipeline = job.pipeline or {}
    return machine.Template(assessment=bool(pipeline.get("assessment")), ai_interview=bool(pipeline.get("ai_interview")), hr_interview=bool(pipeline.get("hr_interview")))


class ApplicationService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.jobs = JobService(db, settings)

    # ------------------------------------------------------------------ lookup
    async def get(self, public_id: int) -> Application:
        application = (await self.db.execute(select(Application).where(Application.public_id == public_id))).scalar_one_or_none()
        if application is None:
            raise NotFoundError("Application not found.", code="APPLICATION_NOT_FOUND")
        return application

    async def get_mine(self, user_id: int, public_id: int) -> Application:
        application = await self.get(public_id)
        if application.user_id != user_id:
            raise NotFoundError("Application not found.", code="APPLICATION_NOT_FOUND")
        return application

    async def get_for_employer(self, auth: AccessTokenClaims, public_id: int) -> tuple[Application, Job]:
        application = await self.get(public_id)
        if not owns_employer(auth, application.employer_org_id):
            raise NotFoundError("Application not found.", code="APPLICATION_NOT_FOUND")
        return application, await self.job_of(application)

    async def job_of(self, application: Application) -> Job:
        job = (await self.db.execute(select(Job).where(Job.id == application.job_id))).scalar_one()
        return job

    async def _locked(self, application: Application) -> Application:
        return (await self.db.execute(select(Application).where(Application.id == application.id).with_for_update().execution_options(populate_existing=True))).scalar_one()

    async def history(self, application: Application) -> list[ApplicationStage]:
        return list((await self.db.execute(select(ApplicationStage).where(ApplicationStage.application_id == application.id).order_by(ApplicationStage.created_at, ApplicationStage.id))).scalars())

    # ------------------------------------------------------------------ applying
    async def apply(self, auth: AccessTokenClaims, job_public_id: int, *, resume_id: int | None = None, cover_note: str | None = None, answers: dict[str, Any] | None = None, career: CareerClient) -> Application:
        """Apply with a resume. Checks, in order: the job is open and visible, the student has a verified skill profile, they are eligible, they
        have not applied. Then the resume is frozen by career-service (outside any transaction) and the application is created."""
        candidates = CandidateService(self.db)
        job = await self.jobs.get(job_public_id)
        visible = (await self.db.execute(select(Job.id).where(Job.id == job.id, JobService.visible_to_students(auth.organization_id)))).first()
        if visible is None:
            # not visible to this student: unknown, closed, paused, past its deadline, from an unverified employer, or restricted elsewhere
            if job.status == JobStatus.OPEN and job.deadline_at and job.deadline_at <= utcnow():
                raise ConflictError("The deadline for this job has passed.", code="DEADLINE_PASSED")
            if job.status in {JobStatus.PAUSED, JobStatus.CLOSED}:
                raise ConflictError("This job is not accepting applications.", code="JOB_NOT_OPEN")
            raise NotFoundError("Job not found.", code="JOB_NOT_FOUND")
        profile = await candidates.profile(auth.user_id, auth.organization_id)
        candidate = to_candidate(profile, user_id=auth.user_id, organization_id=auth.organization_id)
        spec = await self.jobs.spec(job)
        courses = await candidates.course_titles(None)
        verdict = eligibility.check(spec, candidate, course_titles=courses)
        if not verdict.eligible:
            raise _not_eligible(verdict.reasons)
        # Check application config (open date, resume required, custom questions)
        app_config = job.application_config or {}
        open_date_val = app_config.get("open_date")
        if open_date_val:
            try:
                from datetime import datetime, timezone
                od = datetime.fromisoformat(str(open_date_val).replace("Z", "+00:00"))
                if od > utcnow():
                    raise ConflictError("Applications for this job are not open yet.", code="JOB_NOT_OPEN")
            except (ValueError, TypeError):
                pass

        resume_required = app_config.get("resume_required", True)
        if resume_required and not resume_id:
            raise ValidationFailedError(details=[{"field": "resume_id", "code": "REQUIRED", "message": "A resume is required to apply for this job"}])

        questions = app_config.get("questions") or []
        answers_dict = answers or {}
        for q in questions:
            if q.get("required"):
                qid = q.get("id")
                ans = answers_dict.get(qid)
                if ans is None or str(ans).strip() == "":
                    raise ValidationFailedError(details=[{"field": f"answers.{qid}", "code": "REQUIRED", "message": f"Answer to '{q.get('question')}' is required"}])

        existing = (await self.db.execute(select(Application.public_id).where(Application.job_id == job.id, Application.user_id == auth.user_id))).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("You have already applied to this job.", code="ALREADY_APPLIED")
        match = await MatchService(self.db, self.settings).match_for(auth.user_id, job)
        if match is None or match.job_revision != job.revision:
            _, result = MatchService(self.db, self.settings).evaluate(spec, candidate, to_preferences(await candidates.preferences(auth.user_id)), courses)
            match_score, explanation = (result.score, result.explanation) if result else (0, [])
        else:
            match_score, explanation = match.score, list(match.explanation)
        await self.db.commit()  # nothing is held open across the call to career-service
        if resume_id:
            try:
                snapshot = await career.snapshot(resume_id=resume_id, user_id=auth.user_id, label=f"Applied to {job.title}"[:120])
            except Rejected as exc:
                raise ValidationFailedError(details=[{"field": "resume_id", "code": "RESUME_NOT_FOUND", "message": "That is not one of your resumes"}]) from exc
            except Unavailable as exc:
                raise ConflictError("Your resume could not be attached right now. Please try again in a moment.", code="RESUME_UNAVAILABLE") from exc
        else:
            class DummySnapshot:
                version_no = 0
                document = {}
            snapshot = DummySnapshot()
            resume_id = 0

        application = Application(
            public_id=new_public_id(), job_id=job.id, employer_org_id=job.employer_org_id, user_id=auth.user_id, organization_id=auth.organization_id, status=S.APPLIED, status_changed_at=utcnow(),
            cover_note=cover_note, resume_id=resume_id, resume_version_no=snapshot.version_no, resume_snapshot=snapshot.document, match_score=match_score, match_explanation=explanation,
            assessment_revision=0, answers=answers_dict,
        )
        # Ensure UserRef exists
        user_ref = await self.db.get(UserRef, auth.user_id)
        if user_ref is None:
            personal = (snapshot.document or {}).get("personal") or {}
            p_name = personal.get("name", "")
            parts = p_name.split(" ", 1)
            self.db.add(UserRef(
                user_id=auth.user_id,
                first_name=(parts[0] if parts else "")[:100],
                last_name=(parts[1] if len(parts) > 1 else "")[:100],
                email=(personal.get("email") or "")[:320] or None,
                role="student",
                organization_id=auth.organization_id,
                active=True,
            ))
            await self.db.flush()
        self.db.add(application)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            raise ConflictError("You have already applied to this job.", code="ALREADY_APPLIED") from exc
        self.db.add(ApplicationStage(application_id=application.id, from_status=None, to_status=S.APPLIED, actor=Actor.CANDIDATE, actor_user_id=auth.user_id))
        await work_service.enqueue(self.db, WorkKind.SCREEN, application.public_id)
        write_event(
            self.db, event_type="application.created", aggregate_type="application", aggregate_id=application.id,
            payload={
                "application_id": str(application.public_id), "job_id": str(job.public_id), "employer_id": str(job.employer_org_id), "user_id": str(auth.user_id),
                "organization_id": str(auth.organization_id) if auth.organization_id else None, "match_score": match_score, "occurred_at": _iso(utcnow()),
            },
        )
        await self.db.commit()
        return application

    # ------------------------------------------------------------------ moving
    async def move(
        self, application: Application, to: ApplicationStatus, actor: Actor, *, actor_user_id: int | None, note: str | None = None, batch_id: int | None = None,
        job: Job | None = None, locked: bool = False,
    ) -> Application:
        """Move an application if ``actor`` may. Does not commit (the caller does), so a move can be part of a bigger change."""
        if not locked:
            application = await self._locked(application)
        job = job or await self.job_of(application)
        try:
            machine.check(ApplicationStatus(application.status), to, template_of(job), actor)
        except machine.TransitionError as exc:
            raise ConflictError(exc.message, code=exc.code) from exc
        previous = application.status
        application.status, application.status_changed_at = to, utcnow()
        if to in {S.REJECTED, S.WITHDRAWN}:
            application.decision_reason = note
        self.db.add(ApplicationStage(application_id=application.id, from_status=previous, to_status=to, actor=actor, actor_user_id=actor_user_id, note=note, batch_id=batch_id))
        if to == S.ASSESSMENT_INVITED:
            assessment = (job.pipeline or {}).get("assessment") or {}
            application.assessment_test_id = int(assessment["test_id"]) if assessment.get("test_id") else None
            application.assessment_invited_at, application.assessment_invite_state = utcnow(), "pending"
            await work_service.enqueue(self.db, WorkKind.ASSESSMENT_INVITE, application.public_id)
        write_event(
            self.db, event_type="application.stage_changed", aggregate_type="application", aggregate_id=application.id,
            payload={
                "application_id": str(application.public_id), "job_id": str(job.public_id), "employer_id": str(job.employer_org_id), "user_id": str(application.user_id),
                "organization_id": str(application.organization_id) if application.organization_id else None, "from": previous, "to": to.value, "actor": actor.value,
                "interview_plan_id": ((job.pipeline or {}).get("ai_interview") or {}).get("plan_id") if to == S.AI_INTERVIEW_INVITED else None, "occurred_at": _iso(utcnow()),
            },
        )
        return application

    async def transition(self, auth: AccessTokenClaims, application: Application, job: Job, to: ApplicationStatus, *, note: str | None, hr_interview_at: datetime | None) -> Application:
        """A recruiter moves an application to a stage they may name (not offered, placed or rejected: those have their own steps)."""
        if to not in _RECRUITER_TARGETS:
            raise ConflictError(f"Use the dedicated step for {to.value}.", code="USE_DEDICATED_STEP")
        application = await self._locked(application)
        await self._require_job_active(job)
        await self.move(application, to, Actor.RECRUITER, actor_user_id=auth.user_id, note=note, job=job, locked=True)
        if to == S.HR_INTERVIEW:
            application.hr_interview_at, application.hr_interview_note = hr_interview_at, note
        await self.db.commit()
        return application

    async def advance(self, auth: AccessTokenClaims, application: Application, job: Job) -> Application:
        target = machine.default_next(ApplicationStatus(application.status), template_of(job))
        if target is None or target not in _RECRUITER_TARGETS:
            raise ConflictError("There is no single next step from here.", code="NO_DEFAULT_STEP")
        return await self.transition(auth, application, job, target, note=None, hr_interview_at=None)

    async def _require_job_active(self, job: Job) -> None:
        """Pipeline work continues after a job closes, but not while its employer is suspended."""
        employer = (await self.db.execute(select(EmployerProfile).where(EmployerProfile.organization_id == job.employer_org_id))).scalar_one_or_none()
        if employer is None or employer.status == "suspended":
            raise ConflictError("This company is suspended: its hiring is on hold.", code="EMPLOYER_SUSPENDED")

    async def withdraw(self, user_id: int, application: Application, note: str | None) -> Application:
        application = await self._locked(application)
        if application.user_id != user_id:
            raise NotFoundError("Application not found.", code="APPLICATION_NOT_FOUND")
        job = await self.job_of(application)
        if application.status == S.OFFERED:  # withdrawing while an offer is open declines it
            offer = await self._offer(application)
            if offer is not None and offer.status == OfferStatus.EXTENDED:
                offer.status, offer.responded_at, offer.response_note = OfferStatus.DECLINED, utcnow(), note
        await self.move(application, S.WITHDRAWN, Actor.CANDIDATE, actor_user_id=user_id, note=note, job=job, locked=True)
        await self.db.commit()
        return application

    async def _offer(self, application: Application) -> Offer | None:
        return (await self.db.execute(select(Offer).where(Offer.application_id == application.id))).scalar_one_or_none()

    # ------------------------------------------------------------------ rejection: only a person, only a confirmed batch
    async def reject_batch(self, auth: AccessTokenClaims, job: Job, application_ids: list[int], *, reason: str, confirmed: bool, threshold: int | None) -> RejectionBatch:
        """Reject applications in one confirmed batch. ``confirmed`` must be true: it is the person's "yes, these". The batch records how many the
        screening had recommended rejecting and how many it had not, for audit."""
        if not confirmed:
            raise ValidationFailedError(details=[{"field": "confirm", "code": "CONFIRMATION_REQUIRED", "message": "A person must confirm every rejection: send confirm: true"}])
        ids = list(dict.fromkeys(application_ids))
        rows = list(
            (await self.db.execute(select(Application).where(Application.job_id == job.id, Application.public_id.in_(ids)).with_for_update().execution_options(populate_existing=True))).scalars()
        )
        found = {a.public_id for a in rows}
        missing = [i for i in ids if i not in found]
        if missing:
            raise NotFoundError("Some of those applications are not on this job.", code="APPLICATION_NOT_FOUND")
        closed = [a.public_id for a in rows if a.status in TERMINAL_STATUSES]
        if closed:
            raise ConflictError("Some of those applications are already closed.", code="APPLICATION_CLOSED")
        await self._require_job_active(job)
        recommended = sum(1 for a in rows if a.screen_recommendation == "reject")
        batch = RejectionBatch(
            public_id=new_public_id(), job_id=job.id, confirmed_by=auth.user_id, reason=reason, application_ids=ids, recommended_count=recommended,
            not_recommended_count=len(rows) - recommended, threshold=threshold,
        )
        self.db.add(batch)
        await self.db.flush()
        for application in rows:
            if application.status == S.OFFERED:  # an offer withdrawn before it was answered
                offer = await self._offer(application)
                if offer is not None and offer.status == OfferStatus.EXTENDED:
                    offer.status = OfferStatus.WITHDRAWN
            await self.move(application, S.REJECTED, Actor.RECRUITER, actor_user_id=auth.user_id, note=reason, batch_id=batch.public_id, job=job, locked=True)
        await self.db.commit()
        return batch

    async def bulk_shortlist(self, auth: AccessTokenClaims, job: Job, application_ids: list[int]) -> list[Application]:
        rows = list(
            (
                await self.db.execute(
                    select(Application).where(Application.job_id == job.id, Application.public_id.in_(list(dict.fromkeys(application_ids)))).with_for_update().execution_options(populate_existing=True)
                )
            ).scalars()
        )
        if len(rows) != len(set(application_ids)):
            raise NotFoundError("Some of those applications are not on this job.", code="APPLICATION_NOT_FOUND")
        await self._require_job_active(job)
        for application in rows:
            await self.move(application, S.SHORTLISTED, Actor.RECRUITER, actor_user_id=auth.user_id, job=job, locked=True)
        await self.db.commit()
        return rows

    async def shortlist_by_threshold(self, auth: AccessTokenClaims, job: Job, threshold: int) -> list[Application]:
        """A recruiter's own decision to shortlist everyone at or above a screening score (never a rejection)."""
        pending = [
            a.public_id
            for a in (
                await self.db.execute(
                    select(Application).where(Application.job_id == job.id, Application.status.in_([S.APPLIED, S.AI_SCREENED]), Application.screen_score >= threshold)
                )
            ).scalars()
        ]
        return await self.bulk_shortlist(auth, job, pending) if pending else []

    # ------------------------------------------------------------------ recruiter extras
    async def add_note(self, auth: AccessTokenClaims, application: Application, body: str) -> ApplicationNote:
        note = ApplicationNote(application_id=application.id, author_user_id=auth.user_id, body=body)
        self.db.add(note)
        await self.db.commit()
        return note

    async def notes(self, application: Application) -> list[ApplicationNote]:
        return list((await self.db.execute(select(ApplicationNote).where(ApplicationNote.application_id == application.id).order_by(ApplicationNote.created_at))).scalars())

    async def place(self, auth: AccessTokenClaims, application: Application, job: Job) -> Application:
        """Record that the candidate joined. Emits ``candidate.placed``; when placements reach the openings, the job closes itself."""
        application = await self._locked(application)
        await self.move(application, S.PLACED, Actor.RECRUITER, actor_user_id=auth.user_id, job=job, locked=True)
        offer = await self._offer(application)
        write_event(
            self.db, event_type="candidate.placed", aggregate_type="application", aggregate_id=application.id,
            payload={
                "application_id": str(application.public_id), "job_id": str(job.public_id), "employer_id": str(job.employer_org_id), "user_id": str(application.user_id),
                "organization_id": str(application.organization_id) if application.organization_id else None, "title": job.title,
                "ctc": offer.ctc if offer else None, "currency": offer.currency if offer else job.currency, "occurred_at": _iso(utcnow()),
            },
        )
        await self.db.flush()
        await self.jobs.close_if_filled(job)
        await self.db.commit()
        return application

    # ------------------------------------------------------------------ listing
    @staticmethod
    def _search(q: str | None) -> ColumnElement[bool] | None:
        if not q or not q.strip():
            return None
        from sqlalchemy import or_
        pattern = contains_pattern(q.strip().lower())
        return or_(
            func.lower(UserRef.first_name + " " + UserRef.last_name).like(pattern, escape=LIKE_ESCAPE),
            func.lower(UserRef.email).like(pattern, escape=LIKE_ESCAPE),
        )

    async def list_for_job(
        self, job: Job, *, statuses: list[str] | None, min_score: int | None, sort: str, q: str | None, page: int, per_page: int
    ) -> tuple[list[tuple[Application, UserRef | None]], int]:
        stmt = select(Application, UserRef).outerjoin(UserRef, UserRef.user_id == Application.user_id).where(Application.job_id == job.id)
        if statuses:
            stmt = stmt.where(Application.status.in_(statuses))
        if min_score is not None:
            stmt = stmt.where(Application.screen_score >= min_score)
        search = self._search(q)
        if search is not None:
            stmt = stmt.where(search)
        order = {"screen": (Application.screen_score.desc().nullslast(),), "match": (Application.match_score.desc().nullslast(),), "date": (Application.created_at.desc(),), "recent": (Application.created_at.desc(),)}.get(sort, (Application.created_at.desc(),))
        total = int((await self.db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one())
        rows = (await self.db.execute(stmt.order_by(*order, Application.id).limit(per_page).offset((page - 1) * per_page))).all()
        return [(a, u) for a, u in rows], total

    async def list_mine(self, user_id: int, *, status: str | None, page: int, per_page: int, active: bool | None = None) -> tuple[list[tuple[Application, Job]], int]:
        stmt = select(Application, Job).join(Job, Job.id == Application.job_id).where(Application.user_id == user_id)
        if status:
            stmt = stmt.where(Application.status == status)
        if active is not None:
            closed = [s.value for s in TERMINAL_STATUSES]
            stmt = stmt.where(Application.status.not_in(closed) if active else Application.status.in_(closed))
        total = int((await self.db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one())
        rows = (await self.db.execute(stmt.order_by(Application.created_at.desc(), Application.id).limit(per_page).offset((page - 1) * per_page))).all()
        return [(a, j) for a, j in rows], total

    async def list_for_institution(
        self, organization_id: int, *, status: str | None, drive_id: int | None, page: int, per_page: int
    ) -> tuple[list[tuple[Application, Job, UserRef | None]], int]:
        stmt = (
            select(Application, Job, UserRef).join(Job, Job.id == Application.job_id).outerjoin(UserRef, UserRef.user_id == Application.user_id).where(Application.organization_id == organization_id)
        )
        if status:
            stmt = stmt.where(Application.status == status)
        if drive_id is not None:
            stmt = stmt.where(Job.drive_id == drive_id)
        total = int((await self.db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one())
        rows = (await self.db.execute(stmt.order_by(Application.status_changed_at.desc().nullslast(), Application.id).limit(per_page).offset((page - 1) * per_page))).all()
        return [(a, j, u) for a, j, u in rows], total

    async def status_counts(self, job: Job) -> dict[str, int]:
        rows = await self.db.execute(select(Application.status, func.count()).where(Application.job_id == job.id).group_by(Application.status))
        return {status: int(n) for status, n in rows.all()}


def _not_eligible(reasons: list[str]) -> PermissionDeniedError:
    error = PermissionDeniedError("You do not meet this job's eligibility rules.", code="NOT_ELIGIBLE")
    error.details = [{"field": "eligibility", "code": "NOT_ELIGIBLE", "message": reason} for reason in reasons]
    return error

