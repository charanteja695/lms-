"""An organisation's billing profile: the legal name, GSTIN and state a GST invoice needs and user-management's events do not carry."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.security import AccessTokenClaims
from app.models.billing import BillingProfile
from app.models.refs import OrgRef
from app.permissions.policy import owns
from app.services.gstin import valid_gstin


class ProfileService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, auth: AccessTokenClaims, org_id: int) -> BillingProfile:
        if not owns(auth, org_id):
            raise NotFoundError("Billing profile not found.", code="PROFILE_NOT_FOUND")
        profile = await self.db.get(BillingProfile, org_id)
        if profile is None:
            raise NotFoundError("This organisation has not set its billing profile yet.", code="PROFILE_NOT_FOUND")
        return profile

    async def put(self, auth: AccessTokenClaims, org_id: int, fields: dict[str, Any]) -> BillingProfile:
        if not owns(auth, org_id):
            raise NotFoundError("Organisation not found.", code="ORGANIZATION_NOT_FOUND")
        if await self.db.get(OrgRef, org_id) is None:
            raise NotFoundError("Organisation not found.", code="ORGANIZATION_NOT_FOUND")
        gstin = fields.get("gstin")
        if gstin and not valid_gstin(gstin):
            raise ValidationFailedError(details=[{"field": "gstin", "code": "INVALID_GSTIN", "message": "A GSTIN is 15 characters: 2 digits, a PAN, 1 entity digit, Z and a checksum letter or digit"}])
        profile = await self.db.get(BillingProfile, org_id)
        if profile is None:
            profile = BillingProfile(org_id=org_id, **fields, updated_by=auth.user_id)
            self.db.add(profile)
        else:
            for name, value in fields.items():
                setattr(profile, name, value)
            profile.updated_by = auth.user_id
        await self.db.commit()
        return profile
