"""Handlers for events this service consumes from other services (see README "Consumes events").

  course.retired  {"course_id": "<public id>", "version_id": "<public id>"}

Archives any media asset tagged with ``context_type="course_version"`` and a matching
``context_id`` (the tag is set by whoever requested the upload; this service does not
otherwise know catalog-service's data model). Idempotent: archiving an already-archived
asset is a no-op.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.services.media_asset_service import MediaAssetService

logger = logging.getLogger(__name__)


async def handle_course_retired(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    version_id = int(payload["version_id"])
    archived = await MediaAssetService(db, settings).archive_by_context("course_version", version_id)
    if archived:
        logger.info("archived media assets for a retired course version", extra={"extra_fields": {"version_id": version_id, "count": archived}})
