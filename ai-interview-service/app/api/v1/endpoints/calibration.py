"""Calibration against human-rated samples, and the fairness audit of a screening plan (docs/PRODUCT.md §5.8 "Fairness"). A company's own
team calibrates and audits its own plans; careers managers may do this for any plan."""

from fastapi import APIRouter

from app.api.deps import DbSession, GatewayDep, PlanIdParam, RequireEmployerOrManager, SettingsDep, WriteRateLimit
from app.api.presenters import calibration_run_out, calibration_sample_out
from app.api.responses import AUTHENTICATED, errors
from app.schemas.calibration import (
    AuditReportOut,
    AuditReportResponse,
    CalibrationRunPage,
    CalibrationRunResponse,
    CalibrationSamplePage,
    CalibrationSampleRequest,
    CalibrationSampleResponse,
)
from app.services.audit_service import AuditService
from app.services.evaluation_service import EvaluationService

router = APIRouter(prefix="/interview-plans/{plan_id}", tags=["Calibration and fairness"])


@router.post("/calibration/samples", response_model=CalibrationSampleResponse, status_code=201, summary="Add a human-rated sample", responses=errors(*AUTHENTICATED, 404, 422), dependencies=[WriteRateLimit])
async def add_sample(plan_id: PlanIdParam, body: CalibrationSampleRequest, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> CalibrationSampleResponse:
    sample = await AuditService(db, settings).add_sample(
        auth, plan_id, turns=[t.model_dump() for t in body.turns], scores=body.human_scores, recommendation=body.human_recommendation
    )
    return CalibrationSampleResponse(message="Sample added.", sample=calibration_sample_out(sample))


@router.get("/calibration/samples", response_model=CalibrationSamplePage, summary="Human-rated samples", responses=errors(*AUTHENTICATED, 404))
async def list_samples(plan_id: PlanIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> CalibrationSamplePage:
    samples = await AuditService(db, settings).samples(auth, plan_id)
    return CalibrationSamplePage(message="", samples=[calibration_sample_out(s) for s in samples])


@router.post(
    "/calibration/runs", response_model=CalibrationRunResponse, status_code=201, summary="Score every sample with the current model and compare", responses=errors(*AUTHENTICATED, 404, 409),
    dependencies=[WriteRateLimit],
)
async def run_calibration(plan_id: PlanIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep, gateway: GatewayDep) -> CalibrationRunResponse:
    run = await AuditService(db, settings, EvaluationService(db, settings, gateway)).run_calibration(auth, plan_id)
    return CalibrationRunResponse(message="Calibration run complete.", run=calibration_run_out(run))


@router.get("/calibration/runs", response_model=CalibrationRunPage, summary="Past calibration runs", responses=errors(*AUTHENTICATED, 404))
async def list_calibration_runs(plan_id: PlanIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> CalibrationRunPage:
    runs = await AuditService(db, settings).runs(auth, plan_id)
    return CalibrationRunPage(message="", runs=[calibration_run_out(r) for r in runs])


@router.get(
    "/audit", response_model=AuditReportResponse, summary="Fairness audit", responses=errors(*AUTHENTICATED, 404, 409),
    description="Recommendation mix, override rate, evidence quality, the four-fifths comparison across candidates' institutions, and the latest calibration.",
)
async def audit_report(plan_id: PlanIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> AuditReportResponse:
    report = await AuditService(db, settings).report(auth, plan_id)
    return AuditReportResponse(message="", audit=AuditReportOut(**report))
