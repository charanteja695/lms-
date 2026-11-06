"""Interview plans: a company's screening plans for its jobs, and the platform's mock-interview plans (docs/PRODUCT.md §5.8 "Setup").

A draft is edited freely; publishing freezes it (interviews from then on freeze *that* plan and rubric — the same one for every candidate of a
job) and a new version is a fresh draft. ``PlanService`` enforces who may write which kind."""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import DbSession, PlanIdParam, RequireEmployerOrManager, RequireStudent, SettingsDep, WriteRateLimit
from app.api.presenters import plan_out
from app.api.responses import AUTHENTICATED, errors
from app.domain.enums import PlanKind, PlanStatus
from app.schemas.plan import PlanCreate, PlanPage, PlanResponse, PlanUpdate
from app.services.plan_service import PlanService

router = APIRouter(prefix="/interview-plans", tags=["Interview plans"])
student = APIRouter(prefix="/student/mock-plans", tags=["Interviews (student)"])


@router.post(
    "", response_model=PlanResponse, status_code=201, summary="Draft an interview plan", responses=errors(*AUTHENTICATED),
    description="A screening plan (recruiters and admins, for the company's own jobs) or a mock-interview plan (platform careers managers). "
    "Rounds carry the core questions asked to every candidate verbatim; the AI only adds follow-ups.", dependencies=[WriteRateLimit],
)
async def create_plan(body: PlanCreate, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> PlanResponse:
    plan = await PlanService(db, settings).create(auth, body.model_dump())
    return PlanResponse(message="Draft saved.", plan=plan_out(plan))


@router.get("", response_model=PlanPage, summary="My plans", responses=errors(*AUTHENTICATED))
async def list_plans(
    auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep, kind: Annotated[PlanKind | None, Query()] = None, status: Annotated[PlanStatus | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PlanPage:
    plans, total = await PlanService(db, settings).list_managed(auth, kind=kind.value if kind else None, status=status.value if status else None, page=page, per_page=per_page)
    return PlanPage(
        message="", plans=[plan_out(p) for p in plans],
        page_context=PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="created_at", sort_order=SortOrder.DESC),
    )


@router.get("/{plan_id}", response_model=PlanResponse, summary="A plan", responses=errors(*AUTHENTICATED))
async def get_plan(plan_id: PlanIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> PlanResponse:
    plan = await PlanService(db, settings).get_managed(auth, plan_id)
    return PlanResponse(message="", plan=plan_out(plan))


@router.patch("/{plan_id}", response_model=PlanResponse, summary="Edit a draft", responses=errors(*AUTHENTICATED, 409), dependencies=[WriteRateLimit])
async def update_plan(plan_id: PlanIdParam, body: PlanUpdate, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> PlanResponse:
    service = PlanService(db, settings)
    plan = await service.update(await service.get_managed(auth, plan_id), body.model_dump(exclude_unset=True))
    return PlanResponse(message="Saved.", plan=plan_out(plan))


@router.post("/{plan_id}/publish", response_model=PlanResponse, summary="Publish a draft", responses=errors(*AUTHENTICATED, 409), dependencies=[WriteRateLimit])
async def publish_plan(plan_id: PlanIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> PlanResponse:
    service = PlanService(db, settings)
    plan = await service.publish(await service.get_managed(auth, plan_id))
    return PlanResponse(message="Published: this version is now used for new interviews.", plan=plan_out(plan))


@router.post("/{plan_id}/retire", response_model=PlanResponse, summary="Retire a plan", responses=errors(*AUTHENTICATED, 409), dependencies=[WriteRateLimit])
async def retire_plan(plan_id: PlanIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> PlanResponse:
    service = PlanService(db, settings)
    plan = await service.retire(await service.get_managed(auth, plan_id))
    return PlanResponse(message="Retired.", plan=plan_out(plan))


@router.post("/{plan_id}/versions", response_model=PlanResponse, status_code=201, summary="Start a new version", responses=errors(*AUTHENTICATED, 409), dependencies=[WriteRateLimit])
async def new_plan_version(plan_id: PlanIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> PlanResponse:
    service = PlanService(db, settings)
    draft = await service.new_version(auth, await service.get_managed(auth, plan_id))
    return PlanResponse(message="New draft version created.", plan=plan_out(draft))


@student.get("", response_model=PlanPage, summary="Mock-interview plans I can practice with", responses=errors(*AUTHENTICATED))
async def list_mock_plans(
    auth: RequireStudent, db: DbSession, settings: SettingsDep, page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PlanPage:
    plans, total = await PlanService(db, settings).list_mock_for_students(page=page, per_page=per_page)
    return PlanPage(
        message="", plans=[plan_out(p) for p in plans],
        page_context=PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="role", sort_order=SortOrder.ASC),
    )
