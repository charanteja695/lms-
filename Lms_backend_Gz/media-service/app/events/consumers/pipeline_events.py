"""Handles this service's own ``media.uploaded`` event: runs the transcoder (see
app/pipeline/transcoder.py) on the worker, out of the request/response cycle, since a real
clip can take seconds to minutes to encode.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.pipeline import transcoder
from app.services.media_asset_service import MediaAssetService

logger = logging.getLogger(__name__)


async def handle_media_uploaded(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    asset_public_id = int(payload["media_asset_id"])
    service = MediaAssetService(db, settings)
    asset = await service.get(asset_public_id)

    await service.mark_processing(asset)
    try:
        result = await transcoder.process_upload(settings, storage_key=asset.storage_key, asset_public_id=asset.public_id)
    except Exception as exc:  # noqa: BLE001 - a failed transcode must not crash the worker; it's recorded on the asset
        logger.exception("transcode failed", extra={"extra_fields": {"asset_id": asset_public_id}})
        await service.mark_failed(asset, str(exc))
        return

    await service.mark_ready(
        asset,
        duration_seconds=result.duration_seconds,
        renditions=[(r.label, r.storage_key, r.byte_size) for r in result.renditions],
    )
