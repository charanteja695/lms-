"""Employer job-post plans (docs/PRODUCT.md §5.10): an employer admin buys a tier from the price list; billing invoices it at once and, when the
invoice is paid, activates the plan and announces `plan.activated`. Whether a recruiter may post a job is job-portal-service's decision, made
from that event — billing is never asked at request time."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import InvoiceKind, PlanStatus, PriceKind
from app.models.billing import Invoice, OrgPlan
from app.services.invoice_service import InvoiceService
from app.services.outbox import write_event
from app.services.price_service import PriceService


def _iso(value: Any) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


class PlanService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.invoices = InvoiceService(db, settings)

    async def mine(self, org_id: int) -> list[OrgPlan]:
        return list((await self.db.execute(select(OrgPlan).where(OrgPlan.org_id == org_id).order_by(OrgPlan.created_at.desc()))).scalars())

    async def invoice_of(self, plan: OrgPlan) -> Invoice:
        return (await self.db.execute(select(Invoice).where(Invoice.id == plan.invoice_id))).scalar_one()

    async def purchase(self, auth: AccessTokenClaims, tier: str) -> tuple[OrgPlan, Invoice]:
        org_id = auth.organization_id
        if org_id is None:
            raise NotFoundError("Organisation not found.", code="ORGANIZATION_NOT_FOUND")
        price = await PriceService(self.db).by_code(PriceKind.EMPLOYER_PLAN, tier)
        if price is None:
            raise NotFoundError("There is no such plan.", code="PLAN_NOT_FOUND")
        if await self.invoices.profile(org_id) is None:
            raise ConflictError("Set your billing profile first: a GST invoice needs your legal name and state.", code="BILLING_PROFILE_MISSING")
        pending = (await self.db.execute(select(OrgPlan.id).where(OrgPlan.org_id == org_id, OrgPlan.status == PlanStatus.PENDING))).first()
        if pending is not None:
            raise ConflictError("You already have a plan waiting for payment: pay or void its invoice first.", code="PLAN_ALREADY_PENDING")
        plan_public_id = new_public_id()
        invoice = await self.invoices.create_draft(
            org_id=org_id, kind=InvoiceKind.PLAN, source_type="plan", source_id=str(plan_public_id),
            lines=[{"description": f"{price.name} plan ({price.meta['job_posts']} job posts, {price.meta['valid_days']} days)", "quantity": 1, "unit_amount": price.unit_amount}],
        )
        if invoice is None:  # cannot happen for a fresh public id; kept so the type is honest
            raise ConflictError("The invoice could not be created.", code="INVOICE_EXISTS")
        plan = OrgPlan(
            public_id=plan_public_id, org_id=org_id, tier=price.code, job_posts=int(price.meta["job_posts"]), valid_days=int(price.meta["valid_days"]), status=PlanStatus.PENDING, invoice_id=invoice.id,
        )
        self.db.add(plan)
        await self.db.flush()
        invoice = await self.invoices.issue(invoice)  # commits
        return plan, invoice

    async def expire_ended(self, *, limit: int = 200) -> int:
        rows = list(
            (await self.db.execute(select(OrgPlan).where(OrgPlan.status == PlanStatus.ACTIVE, OrgPlan.ends_at < utcnow()).limit(limit).with_for_update(skip_locked=True))).scalars()
        )
        for plan in rows:
            plan.status = PlanStatus.EXPIRED
            write_event(
                self.db, event_type="plan.expired", aggregate_type="org_plan", aggregate_id=plan.id,
                payload={"plan_id": str(plan.public_id), "employer_id": str(plan.org_id), "organization_id": str(plan.org_id), "tier": plan.tier, "occurred_at": _iso(utcnow())},
            )
        await self.db.commit()
        return len(rows)
