from datetime import timedelta
from typing import Any

from lms_common.pagination import paginate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.ids import new_public_id
from app.core.time import utcnow
from app.db.session import commit_or_conflict
from app.domain.enums import AssetKind, AssetStatus
from app.models.media_asset import MediaAsset
from app.models.rendition import Rendition
from app.schemas.common import AssetListQuery
from app.schemas.media_asset import UploadRequest
from app.services.outbox import write_event
from app.storage import s3
from app.storage.keys import original_object_key

_PDF_SIGNATURE = b"%PDF-"

_LOAD_DETAIL = (
    selectinload(MediaAsset.renditions),
    selectinload(MediaAsset.captions),
    selectinload(MediaAsset.transcript),
)


def _kind_for(content_type: str, settings: Settings) -> AssetKind:
    if content_type in settings.ALLOWED_VIDEO_CONTENT_TYPES:
        return AssetKind.VIDEO
    if content_type in settings.ALLOWED_IMAGE_CONTENT_TYPES:
        return AssetKind.IMAGE
    if content_type in settings.ALLOWED_DOCUMENT_CONTENT_TYPES:
        return AssetKind.DOCUMENT
    raise BadRequestError(f"'{content_type}' is not an accepted upload type.", code="UNSUPPORTED_CONTENT_TYPE")


class MediaAssetService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def request_upload(self, actor_user_id: int, data: UploadRequest) -> tuple[MediaAsset, dict[str, Any]]:
        kind = _kind_for(data.content_type, self.settings)
        limit = self.settings.MAX_DOCUMENT_UPLOAD_BYTES if kind == AssetKind.DOCUMENT else self.settings.MAX_UPLOAD_BYTES
        if data.byte_size > limit:
            raise BadRequestError(f"Files larger than {limit:,} bytes are not accepted.", code="FILE_TOO_LARGE")

        asset = MediaAsset(
            public_id=new_public_id(),
            kind=kind,
            original_filename=data.original_filename,
            content_type=data.content_type,
            storage_key="",  # filled in once we know the public_id (the key embeds it)
            status=AssetStatus.UPLOADING,
            context_type=data.context_type,
            context_id=data.context_id,
            created_by=actor_user_id,
        )
        asset.storage_key = original_object_key(asset.public_id, data.original_filename)
        self.db.add(asset)
        await commit_or_conflict(self.db)

        upload_fields = await s3.presign_upload(
            self.settings,
            asset.storage_key,
            content_type=data.content_type,
            max_bytes=limit,
            expires_seconds=self.settings.S3_UPLOAD_URL_EXPIRES_SECONDS,
        )
        upload_fields["expires_at"] = utcnow() + timedelta(seconds=self.settings.S3_UPLOAD_URL_EXPIRES_SECONDS)
        return await self.get(asset.public_id), upload_fields

    async def complete_upload(self, asset: MediaAsset) -> MediaAsset:
        """Confirms the object exists in storage. Video assets then wait for the worker's
        transcoder (triggered by ``media.uploaded``, see app/pipeline/transcoder.py) before
        they're playable; images and PDFs need no encoding, so they're marked ready immediately
        (a PDF only after its first bytes prove it is one)."""
        if asset.status != AssetStatus.UPLOADING:
            raise BadRequestError("This upload was already completed.", code="UPLOAD_ALREADY_COMPLETED")

        try:
            head = await s3.head_object(self.settings, asset.storage_key)
        except s3.ObjectNotFound as exc:
            raise BadRequestError(
                "The file was not found in storage. Upload it before calling complete.", code="UPLOAD_NOT_FOUND"
            ) from exc

        asset.byte_size = int(head["ContentLength"])
        if asset.kind == AssetKind.DOCUMENT and (await s3.read_prefix(self.settings, asset.storage_key, 5)) != _PDF_SIGNATURE:
            # the declared type is only a claim: the bytes must really be a PDF
            await s3.delete_object(self.settings, asset.storage_key)
            await self.mark_failed(asset, "The file is not a PDF.")
            raise BadRequestError("The file is not a valid PDF.", code="INVALID_PDF")
        if asset.kind in (AssetKind.IMAGE, AssetKind.DOCUMENT):
            asset.status = AssetStatus.READY
            self.db.add(Rendition(media_asset_id=asset.id, label="source", storage_key=asset.storage_key, byte_size=asset.byte_size))
            write_event(
                self.db,
                event_type="media.ready",
                aggregate_id=asset.id,
                payload={"media_asset_id": str(asset.public_id), "kind": asset.kind},
            )
        else:
            asset.status = AssetStatus.UPLOADED
            write_event(
                self.db, event_type="media.uploaded", aggregate_id=asset.id, payload={"media_asset_id": str(asset.public_id)}
            )
        await self.db.commit()
        return await self.get(asset.public_id)

    async def mark_processing(self, asset: MediaAsset) -> None:
        if asset.status != AssetStatus.UPLOADED:
            return  # already being processed or moved on; the caller (worker) retries the event
        asset.status = AssetStatus.PROCESSING
        await self.db.commit()

    async def mark_ready(self, asset: MediaAsset, *, duration_seconds: int, renditions: list[tuple[str, str, int]]) -> None:
        """``renditions`` is ``(label, storage_key, byte_size)``. Deletes the raw original once
        compressed renditions exist — keeping both defeats the point of transcoding for cost."""
        asset.duration_seconds = duration_seconds
        for label, storage_key, byte_size in renditions:
            self.db.add(Rendition(media_asset_id=asset.id, label=label, storage_key=storage_key, byte_size=byte_size))
        asset.status = AssetStatus.READY
        write_event(
            self.db,
            event_type="media.ready",
            aggregate_id=asset.id,
            payload={"media_asset_id": str(asset.public_id), "kind": asset.kind, "duration_seconds": duration_seconds},
        )
        await self.db.commit()
        await s3.delete_object(self.settings, asset.storage_key)

    async def mark_failed(self, asset: MediaAsset, reason: str) -> None:
        asset.status = AssetStatus.FAILED
        asset.failed_reason = reason[:500]
        write_event(
            self.db, event_type="media.failed", aggregate_id=asset.id, payload={"media_asset_id": str(asset.public_id), "reason": reason[:500]}
        )
        await self.db.commit()

    async def get(self, asset_public_id: int) -> MediaAsset:
        asset = (
            await self.db.execute(
                select(MediaAsset)
                .where(MediaAsset.public_id == asset_public_id)
                .options(*_LOAD_DETAIL)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if asset is None:
            raise NotFoundError("Media asset not found.", code="MEDIA_ASSET_NOT_FOUND")
        return asset

    async def list_assets(self, query: AssetListQuery) -> tuple[list[MediaAsset], int, bool]:
        stmt = select(MediaAsset).where(MediaAsset.archived_at.is_(None))
        if query.context_type:
            stmt = stmt.where(MediaAsset.context_type == query.context_type)
        if query.context_id:
            stmt = stmt.where(MediaAsset.context_id == query.context_id)
        stmt = stmt.order_by(
            MediaAsset.created_at.desc() if query.sort_order == "desc" else MediaAsset.created_at.asc()
        )
        return await paginate(self.db, stmt, query.page, query.per_page, options=_LOAD_DETAIL)

    async def archive(self, asset: MediaAsset) -> MediaAsset:
        if asset.archived_at is not None:
            return asset
        asset.archived_at = utcnow()
        await self.db.commit()
        return await self.get(asset.public_id)

    async def archive_by_context(self, context_type: str, context_id: int) -> int:
        """Best-effort cleanup when the owning content is retired (see the ``course.retired``
        consumer). Returns the number of assets archived."""
        assets = list(
            (
                await self.db.execute(
                    select(MediaAsset).where(
                        MediaAsset.context_type == context_type,
                        MediaAsset.context_id == context_id,
                        MediaAsset.archived_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        now = utcnow()
        for asset in assets:
            asset.archived_at = now
        await self.db.commit()
        return len(assets)
