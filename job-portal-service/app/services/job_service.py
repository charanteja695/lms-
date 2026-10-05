"""Jobs: drafting, approval, and the lifecycle ``draft → pending_approval → open → paused → closed`` (docs/PRODUCT.md §5.7).

Every change to a job takes a row lock on it first. Anything a match depends on (skills, eligibility, location, pay, description)
bumps ``revision`` and queues a re-match, so a student's recommendations follow the job as it changes.
"""

from datetime import datetime
from typing import Any

from lms_common.pagination import LIKE_ESCAPE, contains_pattern
from sqlalchemy import ColumnElement, Select, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import ApplicationStatus, EmployerStatus, JobStatus, Visibility, WorkKind
from app.matching.model import JobSpec
from app.models.application import Application
from app.models.employer import EmployerProfile
from app.models.job import Job, JobInstitution
from app.models.refs import CourseRef, OrgRef
from app.permissions.policy import owns_employer
from app.services import work_service
from app.services.outbox import write_event

# what a match depends on: changing any of these re-scores the job's candidates
_MATCH_FIELDS = (
    "title", "description", "employment_type", "location_type", "locations", "experience_min_months", "experience_max_months", "ctc_max", "required_skills",
    "preferred_skills", "eligibility", "visibility",
)
_EDITABLE = {JobStatus.DRAFT, JobStatus.PAUSED, JobStatus.OPEN}
_MIN_DESCRIPTION = 50


def _iso(value: Any) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


def eligibility_json(data: dict[str, Any]) -> dict[str, Any]:
    """The stored form: ids as strings (they are 64-bit), institutions kept out (they have their own table)."""
    years = data.get("graduation_years")
    return {
        "graduation_years": {"min": years.get("min"), "max": years.get("max")} if years else None,
        "certificate_course_ids": [str(c) for c in data.get("certificate_course_ids") or []],
        "min_scores": [{"course_id": str(m["course_id"]), "min_percent": float(m["min_percent"])} for m in data.get("min_scores") or []],
    }


def pipeline_json(data: dict[str, Any]) -> dict[str, Any]:
    assessment, interview = data.get("assessment"), data.get("ai_interview")
    return {
        "assessment": {"test_id": str(assessment["test_id"]), "min_percent": assessment.get("min_percent")} if assessment else None,
        "ai_interview": {"plan_id": str(interview["plan_id"])} if interview else None,
        "hr_interview": bool(data.get("hr_interview")),
    }


class JobService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    # ------------------------------------------------------------------ lookup
    async def get(self, public_id: int) -> Job:
        job = (await self.db.execute(select(Job).where(Job.public_id == public_id))).scalar_one_or_none()
        if job is None:
            raise NotFoundError("Job not found.", code="JOB_NOT_FOUND")
        return job

    async def get_for_employer(self, auth: AccessTokenClaims, public_id: int) -> Job:
        """A job the caller may manage: their own employer's (a careers manager: any). Someone else's is a 404, not a 403."""
        job = await self.get(public_id)
        if not owns_employer(auth, job.employer_org_id):
            raise NotFoundError("Job not found.", code="JOB_NOT_FOUND")
        return job

    async def _locked(self, job: Job) -> Job:
        return (await self.db.execute(select(Job).where(Job.id == job.id).with_for_update().execution_options(populate_existing=True))).scalar_one()

    async def institution_ids(self, job: Job) -> list[int]:
        return list((await self.db.execute(select(JobInstitution.organization_id).where(JobInstitution.job_id == job.id).order_by(JobInstitution.organization_id))).scalars())

    async def spec(self, job: Job) -> JobSpec:
        institutions = frozenset(await self.institution_ids(job))
        return JobSpec(
            title=job.title, description=job.description, required_skills=tuple(job.required_skills or ()), preferred_skills=tuple(job.preferred_skills or ()),
            locations=tuple(job.locations or ()), location_type=job.location_type, employment_type=job.employment_type, experience_min_months=job.experience_min_months,
            experience_max_months=job.experience_max_months, ctc_max=job.ctc_max, eligibility=dict(job.eligibility or {}), institution_ids=institutions,
            restricted=job.visibility == Visibility.RESTRICTED,
        )

    # ------------------------------------------------------------------ create / edit
    async def _set_institutions(self, job: Job, institution_ids: list[int]) -> None:
        existing = {row.organization_id: row for row in (await self.db.execute(select(JobInstitution).where(JobInstitution.job_id == job.id))).scalars()}
        wanted = set(institution_ids)
        for org_id, row in existing.items():
            if org_id not in wanted:
                await self.db.delete(row)
        for org_id in wanted - set(existing):
            self.db.add(JobInstitution(job_id=job.id, organization_id=org_id))
        job.visibility = Visibility.RESTRICTED if wanted else Visibility.PUBLIC

    async def create(self, auth: AccessTokenClaims, employer_org_id: int, fields: dict[str, Any]) -> Job:
        job = Job(
            public_id=new_public_id(), employer_org_id=employer_org_id, created_by=auth.user_id, status=JobStatus.DRAFT, revision=0, visibility=Visibility.PUBLIC,
            title=fields["title"], description=fields["description"], employment_type=fields["employment_type"], location_type=fields["location_type"], locations=fields["locations"],
            experience_min_months=fields["experience_min_months"], experience_max_months=fields["experience_max_months"], ctc_min=fields["ctc_min"], ctc_max=fields["ctc_max"],
            currency=fields["currency"], required_skills=fields["required_skills"], preferred_skills=fields["preferred_skills"], openings=fields["openings"], deadline_at=fields["deadline_at"],
            eligibility=eligibility_json(fields["eligibility"]), pipeline=pipeline_json(fields["pipeline"]),
        )
        self.db.add(job)
        await self.db.flush()
        await self._set_institutions(job, [int(i) for i in fields["eligibility"].get("institution_ids") or []])
        await self.db.commit()
        return job

    async def update(self, job: Job, fields: dict[str, Any]) -> Job:
        job = await self._locked(job)
        if job.status == JobStatus.PENDING_APPROVAL:
            raise ConflictError("This job is waiting for approval. Withdraw the submission to edit it.", code="JOB_PENDING")
        if job.status not in _EDITABLE:
            raise ConflictError("A closed job cannot be edited.", code="JOB_CLOSED")
        before = {name: getattr(job, name) for name in _MATCH_FIELDS}
        for name in ("title", "description", "employment_type", "location_type", "locations", "experience_min_months", "experience_max_months", "ctc_min", "ctc_max", "currency", "required_skills", "preferred_skills", "openings", "deadline_at"):
            if name in fields:
                setattr(job, name, fields[name])
        if "eligibility" in fields and fields["eligibility"] is not None:
            job.eligibility = eligibility_json(fields["eligibility"])
            await self._set_institutions(job, [int(i) for i in fields["eligibility"].get("institution_ids") or []])
        if "pipeline" in fields and fields["pipeline"] is not None:
            if job.pipeline != pipeline_json(fields["pipeline"]) and await self._application_count(job) > 0:
                raise ConflictError("The hiring pipeline cannot change once people have applied.", code="PIPELINE_LOCKED")
            job.pipeline = pipeline_json(fields["pipeline"])
        if "openings" in fields and job.openings < await self._placed_count(job):
            raise ConflictError("There are already more placements than that.", code="OPENINGS_BELOW_PLACED")
        if job.location_type != "remote" and not job.locations:
            raise ValidationFailedError(details=[{"field": "locations", "code": "REQUIRED", "message": "Give at least one location (or make the job remote)"}])
        if job.experience_max_months is not None and job.experience_max_months < job.experience_min_months:
            raise ValidationFailedError(details=[{"field": "experience_max_months", "code": "INVALID_RANGE", "message": "The maximum experience is below the minimum"}])
        if job.ctc_min is not None and job.ctc_max is not None and job.ctc_max < job.ctc_min:
            raise ValidationFailedError(details=[{"field": "ctc_max", "code": "INVALID_RANGE", "message": "The maximum pay is below the minimum"}])
        if any(getattr(job, name) != value for name, value in before.items()):
            job.revision += 1
            job.embedding, job.embedding_revision = None, None
            if job.status == JobStatus.OPEN:
                await work_service.enqueue(self.db, WorkKind.MATCH_JOB, job.public_id)
        await self.db.commit()
        return job

    async def _application_count(self, job: Job) -> int:
        return int((await self.db.execute(select(func.count()).select_from(Application).where(Application.job_id == job.id))).scalar_one())

    async def _placed_count(self, job: Job) -> int:
        return int(
            (await self.db.execute(select(func.count()).select_from(Application).where(Application.job_id == job.id, Application.status == ApplicationStatus.PLACED))).scalar_one()
        )

    # ------------------------------------------------------------------ lifecycle
    async def _validate_for_submission(self, job: Job) -> None:
        problems: list[dict[str, str]] = []
        if not job.required_skills:
            problems.append({"field": "required_skills", "code": "REQUIRED", "message": "List at least one required skill: matching needs it"})
        if len((job.description or "").strip()) < _MIN_DESCRIPTION:
            problems.append({"field": "description", "code": "TOO_SHORT", "message": f"Describe the job in at least {_MIN_DESCRIPTION} characters"})
        if job.deadline_at is not None and job.deadline_at <= utcnow():
            problems.append({"field": "deadline_at", "code": "IN_THE_PAST", "message": "The deadline has passed"})
        if len(job.required_skills or []) + len(job.preferred_skills or []) > self.settings.MAX_SKILLS_PER_JOB:
            problems.append({"field": "required_skills", "code": "TOO_MANY_ITEMS", "message": f"At most {self.settings.MAX_SKILLS_PER_JOB} skills in total"})
        rules = job.eligibility or {}
        course_ids = {int(c) for c in rules.get("certificate_course_ids") or []} | {int(m["course_id"]) for m in rules.get("min_scores") or []}
        if course_ids:
            known = set((await self.db.execute(select(CourseRef.course_id).where(CourseRef.course_id.in_(course_ids)))).scalars())
            for missing in sorted(course_ids - known):
                problems.append({"field": "eligibility", "code": "UNKNOWN_COURSE", "message": f"Course {missing} is not a published course"})
        institutions = set(await self.institution_ids(job))
        if institutions:
            known_orgs = set(
                (await self.db.execute(select(OrgRef.org_id).where(OrgRef.org_id.in_(institutions), OrgRef.org_type == "institution", OrgRef.active.is_(True)))).scalars()
            )
            for missing in sorted(institutions - known_orgs):
                problems.append({"field": "eligibility.institution_ids", "code": "UNKNOWN_INSTITUTION", "message": f"Institution {missing} is not an active institution"})
        if problems:
            raise ValidationFailedError(details=problems)

    async def submit(self, job: Job) -> Job:
        job = await self._locked(job)
        if job.status != JobStatus.DRAFT:
            raise ConflictError(f"A {job.status} job cannot be submitted.", code="INVALID_STATE")
        employer = (await self.db.execute(select(EmployerProfile).where(EmployerProfile.organization_id == job.employer_org_id))).scalar_one_or_none()
        if employer is None or employer.status != EmployerStatus.VERIFIED:
            raise ConflictError("Your company profile must be verified before a job can be submitted.", code="EMPLOYER_NOT_VERIFIED")
        await self._validate_for_submission(job)
        job.status, job.submitted_at, job.review_note = JobStatus.PENDING_APPROVAL, utcnow(), None
        await self.db.commit()
        return job

    async def withdraw_submission(self, job: Job) -> Job:
        job = await self._locked(job)
        if job.status != JobStatus.PENDING_APPROVAL:
            raise ConflictError("Only a job waiting for approval can be withdrawn.", code="INVALID_STATE")
        job.status = JobStatus.DRAFT
        await self.db.commit()
        return job

    async def review(self, job: Job, reviewer_user_id: int, *, approve: bool, note: str | None) -> Job:
        job = await self._locked(job)
        if job.status != JobStatus.PENDING_APPROVAL:
            raise ConflictError("Only a submitted job can be reviewed.", code="NOT_PENDING")
        if not approve and not note:
            raise ValidationFailedError(details=[{"field": "note", "code": "REQUIRED", "message": "Say why: the employer reads it"}])
        job.approved_by, job.reviewed_at, job.review_note = reviewer_user_id, utcnow(), note
        if not approve:
            job.status = JobStatus.DRAFT
        else:
            await self._open(job)
        await self.db.commit()
        return job

    async def _open(self, job: Job) -> None:
        job.status, job.published_at, job.closed_reason, job.closed_at = JobStatus.OPEN, job.published_at or utcnow(), None, None
        job.revision += 1
        await work_service.enqueue(self.db, WorkKind.MATCH_JOB, job.public_id)
        write_event(
            self.db, event_type="job.published", aggregate_type="job", aggregate_id=job.id,
            payload={
                "job_id": str(job.public_id), "employer_id": str(job.employer_org_id), "title": job.title, "location_type": job.location_type, "locations": list(job.locations or []),
                "required_skills": list(job.required_skills or []), "visibility": job.visibility, "drive_id": str(job.drive_id) if job.drive_id else None,
                "institution_ids": [str(i) for i in await self.institution_ids(job)], "deadline_at": _iso(job.deadline_at), "occurred_at": _iso(utcnow()),
            },
        )

    async def pause(self, job: Job) -> Job:
        job = await self._locked(job)
        if job.status != JobStatus.OPEN:
            raise ConflictError("Only an open job can be paused.", code="INVALID_STATE")
        job.status = JobStatus.PAUSED
        await self.db.commit()
        return job

    async def resume(self, job: Job) -> Job:
        job = await self._locked(job)
        if job.status != JobStatus.PAUSED:
            raise ConflictError("Only a paused job can be resumed.", code="INVALID_STATE")
        employer = (await self.db.execute(select(EmployerProfile).where(EmployerProfile.organization_id == job.employer_org_id))).scalar_one_or_none()
        if employer is None or employer.status != EmployerStatus.VERIFIED:
            raise ConflictError("The company is not verified, so its jobs cannot be open.", code="EMPLOYER_NOT_VERIFIED")
        if job.deadline_at is not None and job.deadline_at <= utcnow():
            raise ConflictError("The deadline has passed: move it before resuming.", code="DEADLINE_PASSED")
        await self._open(job)
        await self.db.commit()
        return job

    async def close(self, job: Job, reason: str) -> Job:
        job = await self._locked(job)
        if job.status == JobStatus.CLOSED:
            return job
        self._close(job, reason)
        await self.db.commit()
        return job

    def _close(self, job: Job, reason: str) -> None:
        was_open = job.status in {JobStatus.OPEN, JobStatus.PAUSED}
        job.status, job.closed_at, job.closed_reason = JobStatus.CLOSED, utcnow(), reason
        if was_open:
            write_event(
                self.db, event_type="job.closed", aggregate_type="job", aggregate_id=job.id,
                payload={"job_id": str(job.public_id), "employer_id": str(job.employer_org_id), "reason": reason, "occurred_at": _iso(utcnow())},
            )

    async def close_if_filled(self, job: Job) -> bool:
        """When placements reach the number of openings the job closes itself."""
        job = await self._locked(job)
        if job.status in {JobStatus.OPEN, JobStatus.PAUSED} and await self._placed_count(job) >= job.openings:
            self._close(job, "all openings filled")
            return True
        return False

    async def close_expired(self, *, limit: int = 200) -> int:
        """Close open jobs whose deadline has passed (run by the worker)."""
        rows = list(
            (
                await self.db.execute(
                    select(Job).where(Job.status.in_([JobStatus.OPEN, JobStatus.PAUSED]), Job.deadline_at.is_not(None), Job.deadline_at < utcnow()).limit(limit).with_for_update(skip_locked=True)
                )
            ).scalars()
        )
        for job in rows:
            self._close(job, "deadline passed")
        await self.db.commit()
        return len(rows)

    # ------------------------------------------------------------------ listing
    async def list_for_employer(self, employer_org_id: int, *, status: str | None, q: str | None, page: int, per_page: int) -> tuple[list[Job], int]:
        stmt = select(Job).where(Job.employer_org_id == employer_org_id)
        if status:
            stmt = stmt.where(Job.status == status)
        if q:
            stmt = stmt.where(Job.title.ilike(contains_pattern(q.strip()), escape=LIKE_ESCAPE))
        return await self._page(stmt.order_by(Job.created_at.desc(), Job.id), page, per_page)

    async def list_for_review(self, status: str, *, page: int, per_page: int) -> tuple[list[Job], int]:
        return await self._page(select(Job).where(Job.status == status).order_by(Job.submitted_at.asc().nullslast(), Job.id), page, per_page)

    async def _page(self, stmt: Select[Any], page: int, per_page: int) -> tuple[list[Job], int]:
        total = int((await self.db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one())
        rows = (await self.db.execute(stmt.limit(per_page).offset((page - 1) * per_page))).scalars()
        return list(rows), total

    @staticmethod
    def visible_to_students(organization_id: int | None, *, now: datetime | None = None) -> ColumnElement[bool]:
        """Open, before its deadline, from a verified employer, and either public or restricted to this student's institution."""
        now = now or utcnow()
        verified = exists().where(EmployerProfile.organization_id == Job.employer_org_id, EmployerProfile.status == EmployerStatus.VERIFIED)
        allowed = exists().where(JobInstitution.job_id == Job.id, JobInstitution.organization_id == (organization_id if organization_id is not None else -1))
        return and_(Job.status == JobStatus.OPEN, or_(Job.deadline_at.is_(None), Job.deadline_at > now), verified, or_(Job.visibility == Visibility.PUBLIC, allowed))

    async def stats(self, jobs: list[Job]) -> dict[Any, tuple[int, int]]:
        """(applications, placed) per job."""
        if not jobs:
            return {}
        ids = [j.id for j in jobs]
        totals = {job_id: int(n) for job_id, n in (await self.db.execute(select(Application.job_id, func.count()).where(Application.job_id.in_(ids)).group_by(Application.job_id))).all()}
        placed_rows = await self.db.execute(
            select(Application.job_id, func.count()).where(Application.job_id.in_(ids), Application.status == ApplicationStatus.PLACED).group_by(Application.job_id)
        )
        placed = {job_id: int(n) for job_id, n in placed_rows.all()}
        return {job.id: (totals.get(job.id, 0), placed.get(job.id, 0)) for job in jobs}
