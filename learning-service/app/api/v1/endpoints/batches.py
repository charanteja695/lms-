from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import (
    STUDY,
    BatchIdParam,
    CurrentAuth,
    DbSession,
    RedisDep,
    RequireBatchManager,
    SettingsDep,
    ensure_organization_visible,
    institutions_in_care,
    manages_institution,
    sees_all_institutions,
    sees_own_batches,
)
from app.api.responses import errors
from app.core.exceptions import BadRequestError, PermissionDeniedError
from app.core.security import AccessTokenClaims
from app.schemas.batch import BatchCreate, BatchListResponse, BatchOut, BatchResponse
from app.schemas.common import ListQuery
from app.services.batch_service import BatchService
from app.services.enrollment_service import EnrollmentService

router = APIRouter(prefix="/batches", tags=["Batches"])


def _resolve_organization_id(auth: AccessTokenClaims, requested: int | None) -> int:
    if sees_all_institutions(auth):
        if requested is None:
            raise BadRequestError("organization_id is required.", code="ORGANIZATION_ID_REQUIRED")
        if not manages_institution(auth, requested):
            raise PermissionDeniedError("That institution is not one you look after.")
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
    if not (sees_all_institutions(auth) or sees_own_batches(auth)):
        raise PermissionDeniedError()
    organization_ids = institutions_in_care(auth) if sees_all_institutions(auth) else (auth.organization_id or 0,)
    batches, total, is_exact = await BatchService(db, settings, redis).list_batches(query, organization_ids=organization_ids)
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
    # A student reads the batch they are enrolled in (its course title for "My learning"), and no other.
    if not (auth.has_scope(STUDY) and await EnrollmentService(db, settings).is_enrolled(batch, auth.user_id)):
        ensure_organization_visible(auth, batch.organization_id)
    return BatchResponse(message="Batch retrieved successfully.", batch=BatchOut.model_validate(batch))
