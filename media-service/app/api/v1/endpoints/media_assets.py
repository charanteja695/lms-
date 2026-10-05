from typing import Annotated

from fastapi import APIRouter, Depends, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import AssetIdParam, CurrentAuth, DbSession, RequireAuthor, SettingsDep, rate_limit
from app.api.responses import errors
from app.schemas.common import AssetListQuery
from app.schemas.media_asset import (
    MediaAssetListResponse,
    MediaAssetOut,
    MediaAssetResponse,
    UploadFields,
    UploadRequest,
    UploadResponse,
)
from app.services.media_asset_service import MediaAssetService

router = APIRouter(prefix="/media", tags=["Media"])

_upload_rate_limit = rate_limit("media_upload", "UPLOAD_URL_RATE_LIMIT_PER_HOUR", 3_600)


@router.post(
    "/uploads",
    response_model=UploadResponse,
    status_code=201,
    summary="Start a clip upload",
    description="Returns a presigned S3 POST: the browser uploads directly to storage, then calls "
    "POST /media/{asset_id}/complete. Requires content.author.",
    responses=errors(400, 401, 403, 422, 429),
    dependencies=[Depends(_upload_rate_limit)],
)
async def request_upload(data: UploadRequest, auth: RequireAuthor, db: DbSession, settings: SettingsDep) -> UploadResponse:
    asset, upload_fields = await MediaAssetService(db, settings).request_upload(auth.user_id, data)
    return UploadResponse(
        message="Upload started. Upload the file to storage, then call complete.",
        asset=MediaAssetOut.model_validate(asset),
        upload=UploadFields(**upload_fields),
    )


@router.post(
    "/{asset_id}/complete",
    response_model=MediaAssetResponse,
    summary="Confirm an upload finished",
    description="Verifies the object exists in storage, then runs the (currently synchronous, "
    "stubbed) processing pipeline. Requires content.author.",
    responses=errors(400, 401, 403, 404),
)
async def complete_upload(asset_id: AssetIdParam, auth: RequireAuthor, db: DbSession, settings: SettingsDep) -> MediaAssetResponse:
    service = MediaAssetService(db, settings)
    asset = await service.get(asset_id)
    asset = await service.complete_upload(asset)
    return MediaAssetResponse(message="Upload completed.", asset=MediaAssetOut.model_validate(asset))


@router.get("/{asset_id}", response_model=MediaAssetResponse, summary="Get a media asset", responses=errors(401, 404))
async def get_asset(asset_id: AssetIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> MediaAssetResponse:
    asset = await MediaAssetService(db, settings).get(asset_id)
    return MediaAssetResponse(message="Media asset retrieved successfully.", asset=MediaAssetOut.model_validate(asset))


@router.get("", response_model=MediaAssetListResponse, summary="List media assets", responses=errors(401, 422))
async def list_assets(
    query: Annotated[AssetListQuery, Query()], auth: CurrentAuth, db: DbSession, settings: SettingsDep
) -> MediaAssetListResponse:
    assets, total, is_exact = await MediaAssetService(db, settings).list_assets(query)
    return MediaAssetListResponse(
        message="Media assets retrieved successfully.",
        assets=[MediaAssetOut.model_validate(asset) for asset in assets],
        page_context=PageContext.build(
            page=query.page, per_page=query.per_page, total=total, is_exact=is_exact,
            sort_column="created_time", sort_order=SortOrder(query.sort_order),
        ),
    )


@router.delete(
    "/{asset_id}",
    response_model=MediaAssetResponse,
    summary="Archive a media asset",
    description="Marks the asset archived and revokes future playback; storage objects are kept "
    "(see README 'Not yet wired'). Requires content.author.",
    responses=errors(401, 403, 404),
)
async def archive_asset(asset_id: AssetIdParam, auth: RequireAuthor, db: DbSession, settings: SettingsDep) -> MediaAssetResponse:
    service = MediaAssetService(db, settings)
    asset = await service.get(asset_id)
    asset = await service.archive(asset)
    return MediaAssetResponse(message="Media asset archived.", asset=MediaAssetOut.model_validate(asset))
