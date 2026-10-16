"""Placement drives: an institution's head invites an employer; once the employer accepts, the employer's jobs can be attached and are then
visible only to that institution's students, and to its staff and head (docs/PRODUCT.md §5.7)."""

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import ApplicationStatus, DriveStatus, EmployerStatus, JobStatus, WorkKind
from app.models.application import Application
from app.models.employer import EmployerProfile
from app.models.job import Job
from app.models.offer import PlacementDrive
from app.models.refs import OrgRef
from app.permissions.policy import can_manage_careers
from app.services import work_service
from app.services.job_service import JobService
from app.services.outbox import write_event


def _iso(value: Any) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


class DriveService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.jobs = JobService(db, settings)

    async def get(self, public_id: int) -> PlacementDrive:
        drive = (await self.db.execute(select(PlacementDrive).where(PlacementDrive.public_id == public_id))).scalar_one_or_none()
        if drive is None:
            raise NotFoundError("Placement drive not found.", code="DRIVE_NOT_FOUND")
        return drive

    async def get_visible(self, auth: AccessTokenClaims, public_id: int) -> PlacementDrive:
        """A drive its institution's staff, its employer's team, or a careers manager may see; anyone else gets a 404."""
        drive = await self.get(public_id)
        if not (auth.organization_id in {drive.organization_id, drive.employer_org_id} or can_manage_careers(auth)):
            raise NotFoundError("Placement drive not found.", code="DRIVE_NOT_FOUND")
        return drive

    def _event(self, event_type: str, drive: PlacementDrive) -> None:
        write_event(
            self.db, event_type=event_type, aggregate_type="placement_drive", aggregate_id=drive.id,
            payload={
                "drive_id": str(drive.public_id), "organization_id": str(drive.organization_id), "employer_id": str(drive.employer_org_id), "title": drive.title,
                "status": drive.status, "occurred_at": _iso(utcnow()),
            },
        )

    async def propose(self, auth: AccessTokenClaims, employer_org_id: int, *, title: str, description: str | None, drive_date: date | None) -> PlacementDrive:
        employer = (await self.db.execute(select(EmployerProfile).where(EmployerProfile.organization_id == employer_org_id))).scalar_one_or_none()
        org = await self.db.get(OrgRef, employer_org_id)
        if employer is None or employer.status != EmployerStatus.VERIFIED or org is None or org.org_type != "employer":
            raise ValidationFailedError(details=[{"field": "employer_id", "code": "UNKNOWN_EMPLOYER", "message": "Invite a verified company"}])
        drive = PlacementDrive(
            public_id=new_public_id(), organization_id=auth.organization_id or 0, employer_org_id=employer_org_id, title=title, description=description, drive_date=drive_date,
            status=DriveStatus.PROPOSED, created_by=auth.user_id,
        )
        self.db.add(drive)
        await self.db.flush()
        self._event("placement_drive.proposed", drive)
        await self.db.commit()
        return drive

    async def _locked(self, drive: PlacementDrive) -> PlacementDrive:
        return (await self.db.execute(select(PlacementDrive).where(PlacementDrive.id == drive.id).with_for_update().execution_options(populate_existing=True))).scalar_one()

    async def respond(self, auth: AccessTokenClaims, drive: PlacementDrive, *, accept: bool) -> PlacementDrive:
        drive = await self._locked(drive)
        if drive.status != DriveStatus.PROPOSED:
            raise ConflictError("Only a proposed drive can be answered.", code="INVALID_STATE")
        drive.status = DriveStatus.ACCEPTED if accept else DriveStatus.DECLINED
        drive.responded_by, drive.responded_at = auth.user_id, utcnow()
        self._event("placement_drive.accepted" if accept else "placement_drive.declined", drive)
        await self.db.commit()
        return drive

    async def attach_job(self, drive: PlacementDrive, job: Job) -> Job:
        """Restrict one of the employer's jobs to the drive's institution."""
        drive = await self._locked(drive)
        if drive.status != DriveStatus.ACCEPTED:
            raise ConflictError("Jobs can be attached to an accepted drive only.", code="DRIVE_NOT_ACCEPTED")
        if job.employer_org_id != drive.employer_org_id:
            raise NotFoundError("Job not found.", code="JOB_NOT_FOUND")
        if job.status == JobStatus.CLOSED:
            raise ConflictError("A closed job cannot join a drive.", code="JOB_CLOSED")
        if job.drive_id not in (None, drive.public_id):
            raise ConflictError("This job already belongs to another drive.", code="JOB_IN_DRIVE")
        job = await self.jobs._locked(job)
        job.drive_id = drive.public_id
        await self.jobs._set_institutions(job, [drive.organization_id])
        job.revision += 1
        job.embedding, job.embedding_revision = None, None
        if job.status == JobStatus.OPEN:
            await work_service.enqueue(self.db, WorkKind.MATCH_JOB, job.public_id)
        await self.db.commit()
        return job

    async def finish(self, drive: PlacementDrive, *, complete: bool) -> PlacementDrive:
        """Complete a drive (its jobs carry on) or cancel it (its open jobs close: they were only ever for this institution)."""
        drive = await self._locked(drive)
        if drive.status not in {DriveStatus.ACCEPTED, DriveStatus.PROPOSED}:
            raise ConflictError("This drive is already finished.", code="INVALID_STATE")
        drive.status = DriveStatus.COMPLETED if complete else DriveStatus.CANCELLED
        if not complete:
            for job in (await self.db.execute(select(Job).where(Job.drive_id == drive.public_id, Job.status.in_([JobStatus.OPEN, JobStatus.PAUSED, JobStatus.DRAFT, JobStatus.PENDING_APPROVAL])))).scalars():
                self.jobs._close(job, "placement drive cancelled")
        self._event("placement_drive.completed" if complete else "placement_drive.cancelled", drive)
        await self.db.commit()
        return drive

    async def list_for(self, auth: AccessTokenClaims, *, status: str | None, page: int, per_page: int) -> tuple[list[PlacementDrive], int]:
        stmt = select(PlacementDrive)
        if not can_manage_careers(auth):
            stmt = stmt.where(PlacementDrive.organization_id == auth.organization_id) if auth.organization_type == "institution" else stmt.where(PlacementDrive.employer_org_id == auth.organization_id)
        if status:
            stmt = stmt.where(PlacementDrive.status == status)
        total = int((await self.db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one())
        rows = (await self.db.execute(stmt.order_by(PlacementDrive.created_at.desc(), PlacementDrive.id).limit(per_page).offset((page - 1) * per_page))).scalars()
        return list(rows), total

    async def summary(self, drive: PlacementDrive) -> dict[str, Any]:
        """Jobs, applicants by stage and placements of a drive."""
        job_ids = list((await self.db.execute(select(Job.id).where(Job.drive_id == drive.public_id))).scalars())
        counts: dict[str, int] = {}
        if job_ids:
            rows = await self.db.execute(select(Application.status, func.count()).where(Application.job_id.in_(job_ids)).group_by(Application.status))
            counts = {status: int(n) for status, n in rows.all()}
        return {"jobs": len(job_ids), "applications": sum(counts.values()), "by_status": counts, "placed": counts.get(ApplicationStatus.PLACED.value, 0)}
