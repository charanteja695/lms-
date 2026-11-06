"""Calls from other backend services (``X-Internal-Service-Token``), never from a browser."""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select

from app.api.deps import DbSession, SettingsDep
from app.api.responses import errors
from app.core.exceptions import PermissionDeniedError
from app.core.ids import parse_public_id
from app.models.user import User
from app.permissions.roles import Role, UserStatus
from app.schemas.internal import PermissionHoldersRequest, PermissionHoldersResponse
from app.services.permission_service import PermissionService


def require_internal_caller(
    settings: SettingsDep, token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None
) -> None:
    expected = settings.INTERNAL_SERVICE_TOKEN.get_secret_value()
    if not token or not hmac.compare_digest(token.encode(), expected.encode()):
        raise PermissionDeniedError("A valid internal service token is required.", code="INTERNAL_CALLER_REQUIRED")


router = APIRouter(
    prefix="/internal", tags=["Internal"], dependencies=[Depends(require_internal_caller)], responses=errors(403, 422)
)


@router.post(
    "/permission-holders",
    response_model=PermissionHoldersResponse,
    summary="Which of these people hold a permission",
    description="Effective permissions now (role defaults, an admin's scopes, per-person grants and removals; a super admin holds "
    "everything), for active people only. Lets a service check someone other than the caller, e.g. who may be assigned a ticket.",
)
async def permission_holders(body: PermissionHoldersRequest, db: DbSession) -> PermissionHoldersResponse:
    ids = {n for n in (parse_public_id(raw) for raw in body.user_ids) if n is not None}
    users = (
        await db.execute(
            select(User).where(User.public_id.in_(ids), User.status == UserStatus.ACTIVE, User.deleted_at.is_(None))
        )
    ).scalars()
    service = PermissionService(db)
    holders = [
        str(u.public_id)
        for u in users
        if u.role == Role.SUPER_ADMIN or body.permission in await service.effective_for(u)
    ]
    return PermissionHoldersResponse(message="", user_ids=sorted(holders))
