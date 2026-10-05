"""Employer job-post plans: an employer admin buys a tier, pays its invoice, and the plan activates (`plan.activated`)."""

from fastapi import APIRouter

from app.api.deps import DbSession, RequireBillingContact, RequireEmployerAdmin, SettingsDep, WriteRateLimit
from app.api.presenters import invoice_out
from app.api.responses import AUTHENTICATED, errors
from app.domain.enums import PriceKind
from app.schemas.billing import OrgPlanOut, OrgPlanPage, PlanTierOut, PlanTierPage, PurchaseResponse
from app.services.plan_service import PlanService
from app.services.price_service import PriceService

router = APIRouter(prefix="/employer/plans", tags=["Employer plans"])


@router.get("/tiers", response_model=PlanTierPage, summary="Plans on sale", responses=errors(*AUTHENTICATED))
async def list_tiers(auth: RequireBillingContact, db: DbSession) -> PlanTierPage:
    prices, _ = await PriceService(db).list_prices(kind=PriceKind.EMPLOYER_PLAN.value, include_inactive=False, page=1, per_page=100)
    return PlanTierPage(message="", tiers=[PlanTierOut(tier=p.code, name=p.name, price=p.unit_amount, job_posts=int(p.meta["job_posts"]), valid_days=int(p.meta["valid_days"])) for p in prices])


@router.get("", response_model=OrgPlanPage, summary="My company's plans", responses=errors(*AUTHENTICATED))
async def my_plans(auth: RequireEmployerAdmin, db: DbSession, settings: SettingsDep) -> OrgPlanPage:
    return OrgPlanPage(message="", plans=[OrgPlanOut.model_validate(p) for p in await PlanService(db, settings).mine(auth.organization_id or 0)])


@router.post("/{tier}/purchase", response_model=PurchaseResponse, status_code=201, summary="Buy a plan", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit],
             description="Needs a billing profile. Invoices it at once; the plan activates when the invoice is paid.")
async def purchase(tier: str, auth: RequireEmployerAdmin, db: DbSession, settings: SettingsDep) -> PurchaseResponse:
    plan, invoice = await PlanService(db, settings).purchase(auth, tier)
    return PurchaseResponse(message="Invoice issued: pay it to activate the plan.", plan=OrgPlanOut.model_validate(plan), invoice=invoice_out(invoice, settings))
