"""Employer company profiles and their verification by a platform admin (docs/PRODUCT.md §5.7).

``draft → pending → verified | rejected``; a verified employer can be ``suspended`` (by an admin, or because its account was suspended in
user-management) and reinstated. Only a verified employer's jobs can go live, and suspending an employer pauses everything it has open.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.time import utcnow
from app.domain.enums import EmployerStatus, JobStatus
from app.models.employer import EmployerProfile
from app.models.job import Job
from app.models.refs import OrgRef
from app.services.outbox import write_event

_REQUIRED_FOR_SUBMISSION = ("about", "website", "industry")


def _iso(value: Any) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


class EmployerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, organization_id: int) -> EmployerProfile | None:
        return (await self.db.execute(select(EmployerProfile).where(EmployerProfile.organization_id == organization_id))).scalar_one_or_none()

    async def require(self, organization_id: int) -> EmployerProfile:
        profile = await self.get(organization_id)
        if profile is None:
            raise NotFoundError("Employer not found.", code="EMPLOYER_NOT_FOUND")
        return profile

    async def get_or_create(self, organization_id: int) -> EmployerProfile:
        profile = await self.get(organization_id)
        if profile is None:
            org = await self.db.get(OrgRef, organization_id)
            profile = EmployerProfile(
                organization_id=organization_id, industry=org.industry if org else None, status=EmployerStatus.DRAFT, revision=0,
            )
            self.db.add(profile)
            await self.db.flush()
        return profile

    async def company_name(self, organization_id: int) -> str:
        org = await self.db.get(OrgRef, organization_id)
        return org.name if org and org.name else "Company"

    async def open_job_count(self, organization_id: int) -> int:
        return int(
            (await self.db.execute(select(func.count()).select_from(Job).where(Job.employer_org_id == organization_id, Job.status == JobStatus.OPEN))).scalar_one()
        )

    # ------------------------------------------------------------------ the employer's own edits
    async def update(self, organization_id: int, fields: dict[str, Any]) -> EmployerProfile:
        profile = await self.get_or_create(organization_id)
        if profile.status == EmployerStatus.SUSPENDED:
            raise ConflictError("This company is suspended.", code="EMPLOYER_SUSPENDED")
        for name, value in fields.items():
            setattr(profile, name, value)
        if profile.status == EmployerStatus.REJECTED:
            profile.status = EmployerStatus.DRAFT  # editing after a rejection starts a new submission
        profile.revision += 1
        await self.db.commit()
        return profile

    async def submit(self, organization_id: int) -> EmployerProfile:
        profile = await self.get_or_create(organization_id)
        if profile.status in {EmployerStatus.PENDING, EmployerStatus.VERIFIED, EmployerStatus.SUSPENDED}:
            raise ConflictError(f"A {profile.status} company profile cannot be submitted.", code="INVALID_STATE")
        missing = [name for name in _REQUIRED_FOR_SUBMISSION if not getattr(profile, name)]
        if missing:
            raise ValidationFailedError(details=[{"field": name, "code": "REQUIRED", "message": "Fill this in before submitting for verification"} for name in missing])
        profile.status, profile.submitted_at, profile.review_note = EmployerStatus.PENDING, utcnow(), None
        await self.db.commit()
        return profile

    async def manage(self, organization_id: int, fields: dict[str, Any], manager_user_id: int) -> EmployerProfile:
        """The super admin keeps the profile of a company they run: saving it complete verifies it (no one else to ask)."""
        profile = await self.get_or_create(organization_id)
        if profile.status == EmployerStatus.SUSPENDED:
            raise ConflictError("This company is suspended. Reinstate it first.", code="EMPLOYER_SUSPENDED")
        for name, value in fields.items():
            setattr(profile, name, value)
        profile.revision += 1
        missing = [name for name in _REQUIRED_FOR_SUBMISSION if not getattr(profile, name)]
        if missing:
            raise ValidationFailedError(details=[{"field": name, "code": "REQUIRED", "message": "Needed before the company's jobs can go live"} for name in missing])
        if profile.status != EmployerStatus.VERIFIED:
            profile.status, profile.submitted_at, profile.suspension_source = EmployerStatus.VERIFIED, profile.submitted_at or utcnow(), None
            profile.reviewed_by, profile.reviewed_at, profile.review_note = manager_user_id, utcnow(), None
            write_event(
                self.db, event_type="employer_profile.verified", aggregate_type="employer_profile", aggregate_id=profile.id,
                payload={"organization_id": str(organization_id), "reviewed_by": str(manager_user_id), "note": None, "occurred_at": _iso(utcnow())},
            )
        await self.db.commit()
        return profile

    # ------------------------------------------------------------------ the platform's review
    async def review(self, organization_id: int, reviewer_user_id: int, *, approve: bool, note: str | None) -> EmployerProfile:
        profile = await self._locked(organization_id)
        if profile.status != EmployerStatus.PENDING:
            raise ConflictError("Only a submitted company profile can be reviewed.", code="NOT_PENDING")
        if not approve and not note:
            raise ValidationFailedError(details=[{"field": "note", "code": "REQUIRED", "message": "Say why: the employer reads it"}])
        profile.status = EmployerStatus.VERIFIED if approve else EmployerStatus.REJECTED
        profile.reviewed_by, profile.reviewed_at, profile.review_note, profile.suspension_source = reviewer_user_id, utcnow(), note, None
        write_event(
            self.db, event_type="employer_profile.verified" if approve else "employer_profile.rejected", aggregate_type="employer_profile", aggregate_id=profile.id,
            payload={"organization_id": str(organization_id), "reviewed_by": str(reviewer_user_id), "note": note, "occurred_at": _iso(utcnow())},
        )
        await self.db.commit()
        return profile

    async def _locked(self, organization_id: int) -> EmployerProfile:
        row = (
            await self.db.execute(select(EmployerProfile).where(EmployerProfile.organization_id == organization_id).with_for_update().execution_options(populate_existing=True))
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Employer not found.", code="EMPLOYER_NOT_FOUND")
        return row

    async def suspend(self, organization_id: int, *, source: str, by_user_id: int | None, note: str | None) -> tuple[EmployerProfile, int]:
        """Suspend a verified employer and pause every job it has open. Returns ``(profile, jobs paused)``."""
        profile = await self._locked(organization_id)
        if profile.status != EmployerStatus.VERIFIED:
            raise ConflictError("Only a verified company can be suspended.", code="NOT_VERIFIED")
        profile.status, profile.suspension_source, profile.review_note = EmployerStatus.SUSPENDED, source, note
        profile.reviewed_by, profile.reviewed_at = by_user_id, utcnow()
        paused = await self._pause_open_jobs(organization_id, "employer suspended")
        await self.db.commit()
        return profile, paused

    async def reinstate(self, organization_id: int, *, source: str) -> EmployerProfile:
        """Lift a suspension. An account suspension is lifted only by the account's own reactivation, an admin's only by an admin."""
        profile = await self._locked(organization_id)
        if profile.status != EmployerStatus.SUSPENDED:
            raise ConflictError("This company is not suspended.", code="NOT_SUSPENDED")
        if profile.suspension_source != source and source != "admin":
            raise ConflictError("An admin's suspension is lifted by an admin.", code="SUSPENDED_BY_ADMIN")
        profile.status, profile.suspension_source, profile.review_note = EmployerStatus.VERIFIED, None, None
        await self.db.commit()
        return profile

    async def _pause_open_jobs(self, organization_id: int, reason: str) -> int:
        jobs = list((await self.db.execute(select(Job).where(Job.employer_org_id == organization_id, Job.status == JobStatus.OPEN).with_for_update())).scalars())
        for job in jobs:
            job.status, job.closed_reason = JobStatus.PAUSED, reason
        return len(jobs)

    async def list_for_review(self, status: str | None, *, page: int, per_page: int) -> tuple[list[EmployerProfile], int]:
        base = select(EmployerProfile)
        if status:
            base = base.where(EmployerProfile.status == status)
        total = int((await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
        rows = (await self.db.execute(base.order_by(EmployerProfile.submitted_at.asc().nullslast(), EmployerProfile.created_at).limit(per_page).offset((page - 1) * per_page))).scalars()
        return list(rows), total
