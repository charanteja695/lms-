"""Service-to-service endpoints (shared internal token). job-portal-service freezes the resume a candidate applies with."""

from fastapi import APIRouter

from app.api.deps import DbSession, RequireInternalCaller, SettingsDep
from app.api.responses import errors
from app.core.exceptions import NotFoundError
from app.core.ids import parse_public_id
from app.schemas.resume import SnapshotRequest, SnapshotResponse
from app.services.resume_service import ResumeService

router = APIRouter(prefix="/internal", tags=["Internal"], dependencies=[RequireInternalCaller])


@router.post(
    "/resumes/{resume_id}/snapshot", response_model=SnapshotResponse, status_code=201, summary="Freeze a student's resume as a new version and return it",
    description="Requires `X-Internal-Service-Token`. `user_id` must own the resume (`404` otherwise). The version is labelled with `label`, so the student can see "
    "in their version list exactly what was sent with an application.", responses=errors(403, 404, 422),
)
async def snapshot(resume_id: str, body: SnapshotRequest, db: DbSession, settings: SettingsDep) -> SnapshotResponse:
    number = parse_public_id(resume_id)
    if number is None:
        raise NotFoundError("Resume not found.", code="RESUME_NOT_FOUND")
    service = ResumeService(db, settings)
    resume = await service.get(body.user_id, number)
    version = await service.create_version(resume, label=body.label, note=body.note)
    return SnapshotResponse(
        message="Snapshot saved.", resume_id=resume.public_id, user_id=resume.user_id, title=resume.title, target_role=resume.target_role, version_no=version.version_no,
        template_key=version.template_key, ats_score=version.ats_score, document=version.document,
    )
