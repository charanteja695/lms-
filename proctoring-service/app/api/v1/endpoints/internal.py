"""Endpoints for other services, not people: authenticated with the shared internal service token
(``X-Internal-Service-Token``). The AI analysis workers that analyse asynchronously push their findings here."""

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbSession, InternalCaller, SettingsDep, SnapshotIdParam
from app.api.responses import errors
from app.domain.enums import AnalysisStatus, CaseStatus, SessionStatus
from app.models.case import IntegrityCase
from app.models.session import ProctorSession, Snapshot
from app.schemas.proctoring import FindingsIn, QueueOut, QueueResponse, SnapshotOut, SnapshotResponse
from app.services.case_service import CaseService
from app.services.snapshot_service import SnapshotService

router = APIRouter(prefix="/internal", tags=["Internal"], dependencies=[InternalCaller])


@router.post(
    "/snapshots/{snapshot_id}/findings",
    response_model=SnapshotResponse,
    summary="Report the findings of an asynchronous AI analysis",
    description="An empty list means the media was looked at and nothing was found. Findings below `AI_MIN_CONFIDENCE` are "
    "recorded but score nothing; the rest raise weighted risk events in proportion to their confidence. Idempotent: a "
    "repeated push for an analysed snapshot is ignored.",
    responses=errors(401, 403, 404, 422),
)
async def push_findings(snapshot_id: SnapshotIdParam, data: FindingsIn, db: DbSession, settings: SettingsDep) -> SnapshotResponse:
    snapshot = await SnapshotService(db, settings).apply_pushed_findings(snapshot_id, [(f.type, f.confidence, f.detail) for f in data.findings])
    return SnapshotResponse(message="Findings recorded.", snapshot=SnapshotOut.model_validate(snapshot))


@router.get("/queue", response_model=QueueResponse, summary="Work waiting (autoscaling and alerting signal)", responses=errors(401, 403))
async def queue(db: DbSession, settings: SettingsDep) -> QueueResponse:
    pending = (await db.execute(select(func.count()).select_from(Snapshot).where(Snapshot.analysis_status == AnalysisStatus.PENDING))).scalar_one()
    awaiting = (await db.execute(select(func.count()).select_from(ProctorSession).where(ProctorSession.status == SessionStatus.SUBMITTED))).scalar_one()
    open_cases = list((await db.execute(select(IntegrityCase).where(IntegrityCase.status.in_([CaseStatus.OPEN, CaseStatus.UNDER_REVIEW])))).scalars())
    service = CaseService(db, settings)
    return QueueResponse(
        message="Queue depth retrieved successfully.",
        queue=QueueOut(analysis_pending=int(pending), sessions_awaiting_decision=int(awaiting), open_cases=len(open_cases), overdue_cases=sum(1 for c in open_cases if service.overdue(c))),
    )

