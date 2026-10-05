"""An organisation's billing profile: legal name, GSTIN and the state that decides CGST+SGST versus IGST (user-management does not carry these)."""

from fastapi import APIRouter

from app.api.deps import DbSession, OrgIdParam, RequireBillingAdmin, RequireBillingContact, WriteRateLimit
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import NotFoundError
from app.schemas.billing import BillingProfileIn, BillingProfileOut, BillingProfileResponse
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/billing-profile", tags=["Billing profile"])
admin = APIRouter(prefix="/admin/organizations/{org_id}/billing-profile", tags=["Billing profile (admin)"])


@router.get("", response_model=BillingProfileResponse, summary="My organisation's billing profile", responses=errors(*AUTHENTICATED, 404))
async def get_my_profile(auth: RequireBillingContact, db: DbSession) -> BillingProfileResponse:
    if auth.organization_id is None:
        raise NotFoundError("Choose an organisation: billing managers use the admin route.", code="PROFILE_NOT_FOUND")
    return BillingProfileResponse(message="", profile=BillingProfileOut.model_validate(await ProfileService(db).get(auth, auth.organization_id)))


@router.put("", response_model=BillingProfileResponse, summary="Set my organisation's billing profile", responses=errors(*AUTHENTICATED), dependencies=[WriteRateLimit])
async def put_my_profile(body: BillingProfileIn, auth: RequireBillingContact, db: DbSession) -> BillingProfileResponse:
    if auth.organization_id is None:
        raise NotFoundError("Choose an organisation: billing managers use the admin route.", code="PROFILE_NOT_FOUND")
    profile = await ProfileService(db).put(auth, auth.organization_id, body.model_dump())
    return BillingProfileResponse(message="Saved.", profile=BillingProfileOut.model_validate(profile))


@admin.get("", response_model=BillingProfileResponse, summary="An organisation's billing profile", responses=errors(*AUTHENTICATED, 404))
async def get_profile(org_id: OrgIdParam, auth: RequireBillingAdmin, db: DbSession) -> BillingProfileResponse:
    return BillingProfileResponse(message="", profile=BillingProfileOut.model_validate(await ProfileService(db).get(auth, org_id)))


@admin.put("", response_model=BillingProfileResponse, summary="Set an organisation's billing profile", responses=errors(*AUTHENTICATED, 404), dependencies=[WriteRateLimit])
async def put_profile(org_id: OrgIdParam, body: BillingProfileIn, auth: RequireBillingAdmin, db: DbSession) -> BillingProfileResponse:
    profile = await ProfileService(db).put(auth, org_id, body.model_dump())
    return BillingProfileResponse(message="Saved.", profile=BillingProfileOut.model_validate(profile))
