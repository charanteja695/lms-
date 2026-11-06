import logging
import re
from pathlib import Path
from typing import Annotated, Any

import anyio
from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import AssetIdParam, CurrentAuth, DbSession, RequireAuthor, SettingsDep, rate_limit
from app.api.responses import errors
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.ids import new_public_id
from app.db.session import commit_or_conflict
from app.domain.enums import AssetKind, AssetStatus
from app.models.media_asset import MediaAsset
from app.models.rendition import Rendition
from app.schemas.common import AssetListQuery
from app.schemas.media_asset import (
    MediaAssetListResponse,
    MediaAssetOut,
    MediaAssetResponse,
    MediaSummaryOut,
    MediaSummaryResponse,
    UploadFields,
    UploadRequest,
    UploadResponse,
)
from app.services.media_asset_service import MediaAssetService

logger = logging.getLogger("app.media")
router = APIRouter(prefix="/media", tags=["Media"])

_upload_rate_limit = rate_limit("media_upload", "UPLOAD_URL_RATE_LIMIT_PER_HOUR", 3_600)


@router.post(
    "/videos",
    response_model=dict[str, Any],
    status_code=201,
    summary="Direct upload for video lessons",
    description="Uploads video via multipart/form-data. Uses Cloudinary if configured; falls back to streaming storage.",
    responses=errors(400, 401, 403, 422),
)
async def upload_video(
    auth: RequireAuthor,
    db: DbSession,
    settings: SettingsDep,
    file: UploadFile = File(...),
    title: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    course_id: Annotated[str | None, Form()] = None,
    module_id: Annotated[str | None, Form()] = None,
    topic_id: Annotated[str | None, Form()] = None,
    duration_seconds: Annotated[int | None, Form()] = None,
    context_type: Annotated[str | None, Form()] = "topic",
    context_id: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    filename = file.filename or "video.mp4"
    lower_name = filename.lower()
    valid_exts = (".mp4", ".webm", ".mov", ".mkv", ".m4v", ".avi")
    if not (any(lower_name.endswith(ext) for ext in valid_exts) or (file.content_type and file.content_type.startswith("video/"))):
        raise BadRequestError("Only video files (.mp4, .webm, .mov, .mkv) are allowed.", code="INVALID_VIDEO_FORMAT")

    storage_dir = Path(settings.STORAGE_LOCAL_DIR) / "videos"
    storage_dir.mkdir(parents=True, exist_ok=True)
    asset_public_id = new_public_id()
    safe_name = "".join(c for c in filename if c.isalnum() or c in " ._-")[:100] or "video.mp4"
    temp_target = storage_dir / f"{asset_public_id}_{safe_name}"

    total_bytes = 0
    chunk_size = 1024 * 1024  # 1 MB chunk streaming to prevent excessive memory usage
    with open(temp_target, "wb") as out_f:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > settings.MAX_UPLOAD_BYTES:
                out_f.close()
                temp_target.unlink(missing_ok=True)
                raise BadRequestError(f"Video file exceeds {settings.MAX_UPLOAD_BYTES} bytes limit.", code="FILE_TOO_LARGE")
            out_f.write(chunk)

    cloudinary_configured = bool(
        settings.CLOUDINARY_URL
        or (settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET)
    )
    cloudinary_public_id = None
    playback_url = None
    detected_duration = duration_seconds or 0

    if cloudinary_configured:
        try:
            import cloudinary
            import cloudinary.uploader

            if settings.CLOUDINARY_URL:
                cloudinary.config(cloudinary_url=settings.CLOUDINARY_URL)
            else:
                cloudinary.config(
                    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
                    api_key=settings.CLOUDINARY_API_KEY,
                    api_secret=settings.CLOUDINARY_API_SECRET.get_secret_value() if settings.CLOUDINARY_API_SECRET else None,
                    secure=True,
                )

            # Use chunked upload specifically for large videos (> 20 MB)
            result = await anyio.to_thread.run_sync(
                lambda: cloudinary.uploader.upload_large(
                    str(temp_target),
                    resource_type="video",
                    folder="lms/videos",
                    chunk_size=6_000_000,
                )
            )
            playback_url = result.get("secure_url") or result.get("url")
            cloudinary_public_id = result.get("public_id")
            if result.get("duration"):
                detected_duration = int(round(float(result["duration"])))
        except Exception as e:
            logger.warning(f"Cloudinary upload failed ({e}); falling back to local media streaming.")
            playback_url = None

    if not playback_url:
        playback_url = f"/api/v1/media/stream/{asset_public_id}"

    resolved_context_id = None
    if context_id and context_id.isdigit():
        resolved_context_id = int(context_id)
    elif topic_id and topic_id.isdigit():
        resolved_context_id = int(topic_id)

    asset = MediaAsset(
        public_id=asset_public_id,
        kind=AssetKind.VIDEO,
        original_filename=filename,
        content_type=file.content_type or "video/mp4",
        byte_size=total_bytes,
        storage_key=playback_url,
        status=AssetStatus.READY,
        duration_seconds=detected_duration,
        context_type=context_type,
        context_id=resolved_context_id,
        created_by=auth.user_id,
    )
    db.add(asset)
    await db.flush()

    rendition = Rendition(
        media_asset_id=asset.id,
        label="source",
        storage_key=playback_url,
        byte_size=total_bytes,
    )
    db.add(rendition)
    await commit_or_conflict(db)

    return {
        "message": "Video uploaded successfully.",
        "asset": {
            "asset_id": str(asset.public_id),
            "kind": "video",
            "status": "ready",
            "original_filename": asset.original_filename,
            "byte_size": asset.byte_size,
            "playback_url": asset.storage_key,
            "public_id": cloudinary_public_id or str(asset.public_id),
            "duration_seconds": asset.duration_seconds,
        },
        "url": asset.storage_key,
        "public_id": cloudinary_public_id or str(asset.public_id),
        "duration_seconds": asset.duration_seconds,
    }



@router.post(
    "/documents",
    response_model=dict[str, Any],
    status_code=201,
    summary="Direct upload for document and PDF lessons",
    description="Uploads PDF/documents via multipart/form-data.",
    responses=errors(400, 401, 403, 422),
)
async def upload_document(
    auth: RequireAuthor,
    db: DbSession,
    settings: SettingsDep,
    file: UploadFile = File(...),
    title: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    course_id: Annotated[str | None, Form()] = None,
    module_id: Annotated[str | None, Form()] = None,
    topic_id: Annotated[str | None, Form()] = None,
    context_type: Annotated[str | None, Form()] = "topic",
    context_id: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    filename = file.filename or "document.pdf"
    storage_dir = Path(settings.STORAGE_LOCAL_DIR) / "documents"
    storage_dir.mkdir(parents=True, exist_ok=True)
    asset_public_id = new_public_id()
    safe_name = "".join(c for c in filename if c.isalnum() or c in " ._-")[:100] or "document.pdf"
    temp_target = storage_dir / f"{asset_public_id}_{safe_name}"

    total_bytes = 0
    chunk_size = 1024 * 1024
    with open(temp_target, "wb") as out_f:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total_bytes += len(chunk)
            out_f.write(chunk)

    playback_url = f"/api/v1/media/stream/{asset_public_id}"
    resolved_context_id = None
    if context_id and context_id.isdigit():
        resolved_context_id = int(context_id)
    elif topic_id and topic_id.isdigit():
        resolved_context_id = int(topic_id)

    asset = MediaAsset(
        public_id=asset_public_id,
        kind=AssetKind.DOCUMENT,
        original_filename=filename,
        content_type=file.content_type or "application/pdf",
        byte_size=total_bytes,
        storage_key=playback_url,
        status=AssetStatus.READY,
        duration_seconds=0,
        context_type=context_type,
        context_id=resolved_context_id,
        created_by=auth.user_id,
    )
    db.add(asset)
    await db.flush()

    rendition = Rendition(
        media_asset_id=asset.id,
        label="source",
        storage_key=playback_url,
        byte_size=total_bytes,
    )
    db.add(rendition)
    await commit_or_conflict(db)

    return {
        "message": "Document uploaded successfully.",
        "asset": {
            "asset_id": str(asset.public_id),
            "kind": "pdf",
            "status": "ready",
            "original_filename": asset.original_filename,
            "byte_size": asset.byte_size,
            "playback_url": asset.storage_key,
            "public_id": str(asset.public_id),
            "duration_seconds": 0,
        },
        "url": asset.storage_key,
        "public_id": str(asset.public_id),
        "duration_seconds": 0,
    }


@router.post(
    "/images",
    response_model=dict[str, Any],
    status_code=201,
    summary="Direct upload for course thumbnails and images",
    description="Uploads thumbnail image via multipart/form-data (PNG, JPG, WebP, max 5 MB).",
    responses=errors(400, 401, 403, 422),
)
async def upload_image(
    auth: RequireAuthor,
    db: DbSession,
    settings: SettingsDep,
    file: UploadFile = File(...),
    course_id: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    filename = file.filename or "thumbnail.jpg"
    lower_name = filename.lower()
    valid_exts = (".png", ".jpg", ".jpeg", ".webp")
    if not (any(lower_name.endswith(ext) for ext in valid_exts) or (file.content_type and file.content_type.startswith("image/"))):
        raise BadRequestError("Only image files (.png, .jpg, .jpeg, .webp) up to 5 MB are allowed.", code="INVALID_IMAGE_FORMAT")

    storage_dir = Path(settings.STORAGE_LOCAL_DIR) / "images"
    storage_dir.mkdir(parents=True, exist_ok=True)
    asset_public_id = new_public_id()
    safe_name = "".join(c for c in filename if c.isalnum() or c in " ._-")[:100] or "thumbnail.jpg"
    temp_target = storage_dir / f"{asset_public_id}_{safe_name}"

    total_bytes = 0
    chunk_size = 512 * 1024
    with open(temp_target, "wb") as out_f:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > 5 * 1024 * 1024:
                out_f.close()
                temp_target.unlink(missing_ok=True)
                raise BadRequestError("Image exceeds 5 MB limit.", code="FILE_TOO_LARGE")
            out_f.write(chunk)

    playback_url = f"/api/v1/media/stream/{asset_public_id}"
    resolved_context_id = int(course_id) if course_id and course_id.isdigit() else None

    asset = MediaAsset(
        public_id=asset_public_id,
        kind=AssetKind.IMAGE,
        original_filename=filename,
        content_type=file.content_type or "image/jpeg",
        byte_size=total_bytes,
        storage_key=playback_url,
        status=AssetStatus.READY,
        duration_seconds=0,
        context_type="course_thumbnail",
        context_id=resolved_context_id,
        created_by=auth.user_id,
    )
    db.add(asset)
    await db.flush()

    rendition = Rendition(
        media_asset_id=asset.id,
        label="source",
        storage_key=playback_url,
        byte_size=total_bytes,
    )
    db.add(rendition)
    await commit_or_conflict(db)

    return {
        "message": "Thumbnail uploaded successfully.",
        "asset": {
            "asset_id": str(asset.public_id),
            "kind": "image",
            "status": "ready",
            "original_filename": asset.original_filename,
            "byte_size": asset.byte_size,
            "playback_url": asset.storage_key,
            "public_id": str(asset.public_id),
            "duration_seconds": 0,
        },
        "url": asset.storage_key,
        "public_id": str(asset.public_id),
    }


@router.get(
    "/stream/{asset_id}",
    summary="Stream video with HTTP Range support",
    responses=errors(404),
)
async def stream_media(asset_id: AssetIdParam, db: DbSession, settings: SettingsDep, request: Request) -> Response:
    asset = await MediaAssetService(db, settings).get(asset_id)
    if not asset or asset.archived_at is not None:
        raise NotFoundError("Video not found or archived.", code="MEDIA_NOT_FOUND")

    # If it is an external URL (e.g. Cloudinary), redirect immediately
    if asset.storage_key.startswith("http://") or asset.storage_key.startswith("https://"):
        return RedirectResponse(asset.storage_key, status_code=307)

    subfolder = "images" if asset.kind == AssetKind.IMAGE else ("documents" if asset.kind == AssetKind.DOCUMENT else "videos")
    storage_dir = Path(settings.STORAGE_LOCAL_DIR) / subfolder
    matching = list(storage_dir.glob(f"{asset.public_id}_*"))
    if not matching or not matching[0].exists():
        for alt in ("images", "documents", "videos"):
            alt_m = list((Path(settings.STORAGE_LOCAL_DIR) / alt).glob(f"{asset.public_id}_*"))
            if alt_m and alt_m[0].exists():
                matching = alt_m
                break
    if not matching or not matching[0].exists():
        raise NotFoundError("Media file not found on disk.", code="FILE_NOT_FOUND")

    file_path = matching[0]
    file_size = file_path.stat().st_size
    content_type = asset.content_type or "video/mp4"
    range_header = request.headers.get("range")

    if range_header:
        match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if match:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else file_size - 1
            start = max(0, start)
            end = min(file_size - 1, end)
            content_length = end - start + 1

            def chunk_generator():
                with open(file_path, "rb") as f:
                    f.seek(start)
                    remaining = content_length
                    while remaining > 0:
                        read_len = min(64 * 1024, remaining)
                        data = f.read(read_len)
                        if not data:
                            break
                        remaining -= len(data)
                        yield data

            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Content-Type": content_type,
                "Content-Disposition": "inline",
                "X-Content-Type-Options": "nosniff",
            }
            return StreamingResponse(chunk_generator(), status_code=206, headers=headers)

    def full_generator():
        with open(file_path, "rb") as f:
            while chunk := f.read(64 * 1024):
                yield chunk

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
        "Content-Type": content_type,
        "Content-Disposition": "inline",
        "X-Content-Type-Options": "nosniff",
    }
    return StreamingResponse(full_generator(), status_code=200, headers=headers)


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


@router.get(
    "/summary",
    response_model=MediaSummaryResponse,
    summary="How many videos and PDFs there are, and their size",
    description="Requires content.author.",
    responses=errors(401, 403),
)
async def summary(auth: RequireAuthor, db: DbSession, settings: SettingsDep) -> MediaSummaryResponse:
    data = await MediaAssetService(db, settings).summary()
    return MediaSummaryResponse(message="Media summary retrieved successfully.", summary=MediaSummaryOut(**data))


@router.post(
    "/{asset_id}/restore",
    response_model=MediaAssetResponse,
    summary="Bring an archived media asset back",
    description="Requires content.author.",
    responses=errors(401, 403, 404),
)
async def restore_asset(asset_id: AssetIdParam, auth: RequireAuthor, db: DbSession, settings: SettingsDep) -> MediaAssetResponse:
    service = MediaAssetService(db, settings)
    asset = await service.restore(await service.get(asset_id))
    return MediaAssetResponse(message="Media asset restored.", asset=MediaAssetOut.model_validate(asset))


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
