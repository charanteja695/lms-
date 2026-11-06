"""Scheduled reports: save a dashboard + filters + a schedule, and the worker runs it when due
(docs/PRODUCT.md §5.9 "Scheduled reports"). ``POST .../run-now`` runs it immediately instead of waiting."""

from fastapi import APIRouter, Response

from app.api.deps import CurrentAuth, DbSession, ReportIdParam, SettingsDep, WriteRateLimit
from app.api.presenters import report_out, report_run_out
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import ConflictError, NotFoundError
from app.core.ids import parse_public_id
from app.domain.enums import ReportStatus
from app.schemas.report import ReportCreate, ReportPage, ReportResponse, ReportRunPage, ReportRunResponse
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("", response_model=ReportResponse, status_code=201, summary="Save a scheduled report", responses=errors(*AUTHENTICATED, 403), dependencies=[WriteRateLimit])
async def create_report(body: ReportCreate, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> ReportResponse:
    filters = {"organization_id": parse_public_id(body.filters.organization_id) if body.filters.organization_id else None, "employer_id": parse_public_id(body.filters.employer_id) if body.filters.employer_id else None}
    definition = await ReportService(db, settings).create(auth, name=body.name, dashboard=body.dashboard.value, filters=filters, frequency=body.frequency.value, report_format=body.format.value)
    return ReportResponse(message="Report saved: it will run on schedule.", report=report_out(definition))


@router.get("", response_model=ReportPage, summary="My saved reports", responses=errors(*AUTHENTICATED))
async def list_reports(auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> ReportPage:
    return ReportPage(message="", reports=[report_out(r) for r in await ReportService(db, settings).list_mine(auth)])


@router.get("/{report_id}", response_model=ReportResponse, summary="A saved report", responses=errors(*AUTHENTICATED, 404))
async def get_report(report_id: ReportIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> ReportResponse:
    definition = await ReportService(db, settings).get_owned(auth, report_id)
    return ReportResponse(message="", report=report_out(definition))


@router.post("/{report_id}/deactivate", response_model=ReportResponse, summary="Stop running a report", responses=errors(*AUTHENTICATED, 404), dependencies=[WriteRateLimit])
async def deactivate_report(report_id: ReportIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> ReportResponse:
    service = ReportService(db, settings)
    definition = await service.deactivate(await service.get_owned(auth, report_id))
    return ReportResponse(message="Deactivated.", report=report_out(definition))


@router.post("/{report_id}/run-now", response_model=ReportRunResponse, status_code=201, summary="Run it immediately", responses=errors(*AUTHENTICATED, 404), dependencies=[WriteRateLimit])
async def run_now(report_id: ReportIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> ReportRunResponse:
    service = ReportService(db, settings)
    run = await service.run_now(await service.get_owned(auth, report_id))
    return ReportRunResponse(message="Run complete." if run.status == ReportStatus.READY else "Run failed.", run=report_run_out(run))


@router.get("/{report_id}/runs", response_model=ReportRunPage, summary="Past runs", responses=errors(*AUTHENTICATED, 404))
async def list_runs(report_id: ReportIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> ReportRunPage:
    service = ReportService(db, settings)
    definition = await service.get_owned(auth, report_id)
    return ReportRunPage(message="", runs=[report_run_out(r) for r in await service.runs(definition)])


@router.get("/{report_id}/runs/{run_id}/download", summary="Download a run's rendered file", responses=errors(*AUTHENTICATED, 404, 409))
async def download_run(report_id: ReportIdParam, run_id: str, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> Response:
    service = ReportService(db, settings)
    definition = await service.get_owned(auth, report_id)
    number = parse_public_id(run_id)
    if number is None:
        raise NotFoundError("Report run not found.", code="REPORT_RUN_NOT_FOUND")
    run = await service.get_run(definition, number)
    if run.status != ReportStatus.READY or run.content is None:
        raise ConflictError("This run has no file to download.", code="RUN_NOT_READY")
    extension = "json" if run.content_type == "application/json" else "csv"
    return Response(content=run.content, media_type=run.content_type or "application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{definition.name}-{run.public_id}.{extension}"'})
