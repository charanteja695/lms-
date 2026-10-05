"""Per-org quota admin API (docs/PRODUCT.md §6: "quotas & cost per org"). Reading limits and usage is open to
the org's own institution staff/head as well as a platform AI manager (``can_view_org_usage``); changing limits
is a platform-only action (``ai.manage``)."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import (
    AdminRateLimit,
    DbSession,
    OrganizationIdParam,
    RequireAiManager,
    RequireViewOrgUsage,
    SettingsDep,
)
from app.api.responses import errors
from app.core.time import period_of, utcnow
from app.models.quota import OrgQuota
from app.schemas.quota import QuotaOut, QuotaResponse, QuotaSetIn, UsageOut, UsageResponse
from app.services.quota_service import QuotaService

router = APIRouter(prefix="/orgs", tags=["Quotas"])


@router.get("/{organization_id}/quota", response_model=QuotaResponse, summary="Get an org's quota limits", responses=errors(401, 403, 429))
async def get_quota(organization_id: OrganizationIdParam, auth: RequireViewOrgUsage, db: DbSession, settings: SettingsDep) -> QuotaResponse:
    row = await db.get(OrgQuota, organization_id)
    out = QuotaOut(
        organization_id=organization_id,
        monthly_token_limit=(row.monthly_token_limit if row and row.monthly_token_limit is not None else settings.DEFAULT_MONTHLY_TOKEN_LIMIT),
        monthly_request_limit=(row.monthly_request_limit if row and row.monthly_request_limit is not None else settings.DEFAULT_MONTHLY_REQUEST_LIMIT),
        monthly_budget_cents=(row.monthly_budget_cents if row and row.monthly_budget_cents is not None else settings.DEFAULT_MONTHLY_BUDGET_CENTS),
        enabled=row.enabled if row else True,
        is_default=row is None,
    )
    return QuotaResponse(message="", quota=out)


@router.put("/{organization_id}/quota", response_model=QuotaResponse, dependencies=[AdminRateLimit], summary="Set an org's quota limits", responses=errors(401, 403, 422, 429))
async def set_quota(organization_id: OrganizationIdParam, body: QuotaSetIn, auth: RequireAiManager, db: DbSession, settings: SettingsDep) -> QuotaResponse:
    row = await db.get(OrgQuota, organization_id)
    if row is None:
        row = OrgQuota(organization_id=organization_id)
        db.add(row)
    row.monthly_token_limit = body.monthly_token_limit
    row.monthly_request_limit = body.monthly_request_limit
    row.monthly_budget_cents = body.monthly_budget_cents
    row.enabled = body.enabled
    row.updated_by = auth.user_id
    await db.commit()
    out = QuotaOut(
        organization_id=organization_id,
        monthly_token_limit=row.monthly_token_limit if row.monthly_token_limit is not None else settings.DEFAULT_MONTHLY_TOKEN_LIMIT,
        monthly_request_limit=row.monthly_request_limit if row.monthly_request_limit is not None else settings.DEFAULT_MONTHLY_REQUEST_LIMIT,
        monthly_budget_cents=row.monthly_budget_cents if row.monthly_budget_cents is not None else settings.DEFAULT_MONTHLY_BUDGET_CENTS,
        enabled=row.enabled, is_default=False,
    )
    return QuotaResponse(message="Quota updated.", quota=out)


@router.get("/{organization_id}/usage", response_model=UsageResponse, summary="Get an org's usage for a period", responses=errors(401, 403, 429))
async def get_usage(
    organization_id: OrganizationIdParam, auth: RequireViewOrgUsage, db: DbSession, settings: SettingsDep,
    period: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$", description="YYYY-MM; defaults to the current period")] = None,
) -> UsageResponse:
    resolved_period = period or period_of(utcnow())
    row, limits = await QuotaService(db, settings).usage(organization_id, resolved_period)
    out = UsageOut(
        organization_id=organization_id, period=resolved_period,
        requests_used=row.requests_used if row else 0, prompt_tokens_used=row.prompt_tokens_used if row else 0,
        completion_tokens_used=row.completion_tokens_used if row else 0, cost_cents_used=row.cost_cents_used if row else 0,
        token_limit=limits.token_limit, request_limit=limits.request_limit, budget_cents=limits.budget_cents,
    )
    return UsageResponse(message="", usage=out)
