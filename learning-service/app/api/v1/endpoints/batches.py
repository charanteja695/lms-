from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import (
    BatchIdParam,
    CurrentAuth,
    DbSession,
    RedisDep,
    RequireBatchManager,
    SettingsDep,
    ensure_organization_visible,
)
from app.api.responses import errors
from app.core.exceptions import BadRequestError
from app.core.security import AccessTokenClaims
from app.permissions.scopes import Scope
from app.schemas.batch import BatchCreate, BatchListResponse, BatchOut, BatchResponse
from app.schemas.common import ListQuery
from app.services.batch_service import BatchService

router = APIRouter(prefix="/batches", tags=["Batches"])


def _resolve_organization_id(auth: AccessTokenClaims, requested: int | None) -> int:
    if auth.has_scope(Scope.ACCOUNTS_MANAGE.value):
        if requested is None:
            raise BadRequestError("organization_id is required.", code="ORGANIZATION_ID_REQUIRED")
        return requested
    if requested is not None and requested != auth.organization_id:
        raise BadRequestError("You can only create batches for your own institution.", code="ORGANIZATION_MISMATCH")
    assert auth.organization_id is not None  # require_batch_manager already guarantees this
    return auth.organization_id


@router.post("", response_model=BatchResponse, status_code=201, summary="Create a batch", responses=errors(400, 401, 403, 404, 409, 422))
async def create_batch(data: BatchCreate, auth: RequireBatchManager, db: DbSession, settings: SettingsDep, redis: RedisDep) -> BatchResponse:
    organization_id = _resolve_organization_id(auth, data.organization_id)
    batch = await BatchService(db, settings, redis).create(auth.user_id, organization_id, data)
    return BatchResponse(message="Batch created successfully.", batch=BatchOut.model_validate(batch))


@router.get("", response_model=BatchListResponse, summary="List batches", responses=errors(401, 422))
async def list_batches(query: Annotated[ListQuery, Query()], auth: CurrentAuth, db: DbSession, settings: SettingsDep, redis: RedisDep) -> BatchListResponse:
    organization_id = None if auth.has_scope(Scope.ACCOUNTS_MANAGE.value) else auth.organization_id
    batches, total, is_exact = await BatchService(db, settings, redis).list_batches(query, organization_id=organization_id)
    return BatchListResponse(
        message="Batches retrieved successfully.",
        batches=[BatchOut.model_validate(batch) for batch in batches],
        page_context=PageContext.build(
            page=query.page, per_page=query.per_page, total=total, is_exact=is_exact,
            sort_column="created_time", sort_order=SortOrder(query.sort_order),
        ),
    )


@router.get("/{batch_id}", response_model=BatchResponse, summary="Get a batch", responses=errors(401, 403, 404))
async def get_batch(batch_id: BatchIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep, redis: RedisDep) -> BatchResponse:
    batch = await BatchService(db, settings, redis).get(batch_id)
    ensure_organization_visible(auth, batch.organization_id)
    return BatchResponse(message="Batch retrieved successfully.", batch=BatchOut.model_validate(batch))
