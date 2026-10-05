"""The seven dashboards (docs/PRODUCT.md §5.9). Every number here is a sum of `DailyRollup` rows kept close
to live by the worker's periodic tick (see the README for what "near-real-time" means); nothing is computed
ad hoc at request time beyond that sum."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentAuth, DbSession
from app.api.responses import AUTHENTICATED, errors
from app.core.ids import parse_public_id
from app.schemas.dashboard import (
    AIUsageDashboardResponse,
    BillingDashboardResponse,
    ContentDashboardResponse,
    ExamIntegrityDashboardResponse,
    HiringDashboardResponse,
    InstitutionDashboardResponse,
    SupportDashboardResponse,
)
from app.services import dashboard_service
from app.services.report_service import check_dashboard_access
from app.services.rollup_query import date_range

router = APIRouter(prefix="/dashboards", tags=["Dashboards"])

Days = Annotated[int, Query(ge=1, le=90, description="How many trailing days, including today")]


def _org(auth: CurrentAuth, organization_id: str | None) -> int | None:
    if organization_id is not None:
        return parse_public_id(organization_id)
    return auth.organization_id


@router.get("/institution", response_model=InstitutionDashboardResponse, summary="An institution's own funnel", responses=errors(*AUTHENTICATED))
async def institution_dashboard(auth: CurrentAuth, db: DbSession, days: Days = 7, organization_id: Annotated[str | None, Query()] = None) -> InstitutionDashboardResponse:
    org = _org(auth, organization_id) or 0
    check_dashboard_access(auth, "institution", organization_id=org, employer_id=None)
    since, until = date_range(days)
    return InstitutionDashboardResponse(message="", dashboard=await dashboard_service.institution(db, organization_id=org, since=since, until=until))


@router.get("/content", response_model=ContentDashboardResponse, summary="Platform-wide learning funnel", responses=errors(*AUTHENTICATED))
async def content_dashboard(auth: CurrentAuth, db: DbSession, days: Days = 7) -> ContentDashboardResponse:
    check_dashboard_access(auth, "content", organization_id=None, employer_id=None)
    since, until = date_range(days)
    return ContentDashboardResponse(message="", dashboard=await dashboard_service.content(db, since=since, until=until))


@router.get("/exam-integrity", response_model=ExamIntegrityDashboardResponse, summary="Exam and integrity trends", responses=errors(*AUTHENTICATED))
async def exam_integrity_dashboard(auth: CurrentAuth, db: DbSession, days: Days = 7) -> ExamIntegrityDashboardResponse:
    check_dashboard_access(auth, "exam_integrity", organization_id=None, employer_id=None)
    since, until = date_range(days)
    return ExamIntegrityDashboardResponse(message="", dashboard=await dashboard_service.exam_integrity(db, since=since, until=until))


@router.get("/support", response_model=SupportDashboardResponse, summary="Ticket volume, SLAs and CSAT", responses=errors(*AUTHENTICATED))
async def support_dashboard(auth: CurrentAuth, db: DbSession, days: Days = 7, organization_id: Annotated[str | None, Query()] = None) -> SupportDashboardResponse:
    check_dashboard_access(auth, "support", organization_id=None, employer_id=None)
    since, until = date_range(days)
    return SupportDashboardResponse(message="", dashboard=await dashboard_service.support(db, organization_id=parse_public_id(organization_id) if organization_id else None, since=since, until=until))


@router.get(
    "/hiring", response_model=HiringDashboardResponse, summary="Hiring funnel", responses=errors(*AUTHENTICATED),
    description="Platform-wide for a careers manager, or one employer's own jobs for that employer's own team (send no `employer_id`: it defaults to the caller's).",
)
async def hiring_dashboard(
    auth: CurrentAuth, db: DbSession, days: Days = 7, employer_id: Annotated[str | None, Query()] = None, organization_id: Annotated[str | None, Query()] = None
) -> HiringDashboardResponse:
    employer = parse_public_id(employer_id) if employer_id else (auth.organization_id if auth.role in {"employer_admin", "recruiter"} else None)
    org = parse_public_id(organization_id) if organization_id else None
    check_dashboard_access(auth, "hiring", organization_id=org, employer_id=employer)
    since, until = date_range(days)
    return HiringDashboardResponse(message="", dashboard=await dashboard_service.hiring(db, employer_id=employer, organization_id=org, since=since, until=until))


@router.get("/ai-usage", response_model=AIUsageDashboardResponse, summary="AI requests, tokens and cost", responses=errors(*AUTHENTICATED))
async def ai_usage_dashboard(auth: CurrentAuth, db: DbSession, days: Days = 7, organization_id: Annotated[str | None, Query()] = None) -> AIUsageDashboardResponse:
    check_dashboard_access(auth, "ai_usage", organization_id=None, employer_id=None)
    since, until = date_range(days)
    return AIUsageDashboardResponse(message="", dashboard=await dashboard_service.ai_usage(db, organization_id=parse_public_id(organization_id) if organization_id else None, since=since, until=until))


@router.get("/billing", response_model=BillingDashboardResponse, summary="Invoiced vs collected revenue", responses=errors(*AUTHENTICATED))
async def billing_dashboard(auth: CurrentAuth, db: DbSession, days: Days = 7, organization_id: Annotated[str | None, Query()] = None) -> BillingDashboardResponse:
    check_dashboard_access(auth, "billing", organization_id=None, employer_id=None)
    since, until = date_range(days)
    return BillingDashboardResponse(message="", dashboard=await dashboard_service.billing(db, organization_id=parse_public_id(organization_id) if organization_id else None, since=since, until=until))
