from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.ids import new_public_id
from app.core.time import utcnow
from app.core.tokens import generate_secure_token, hash_token
from app.db.session import commit_or_conflict
from app.domain.enums import AssetKind, AssetStatus
from app.models.media_asset import MediaAsset
from app.models.playback_token import PlaybackToken
from app.models.rendition import Rendition
from app.storage import s3

# No adaptive-bitrate player yet (see README "Not yet wired"): one rendition is served per
# request, so pick the best available rather than assuming a fixed label exists.
_RENDITION_PREFERENCE = ("1080p", "720p", "480p", "native", "source")


def _best_rendition(renditions: list[Rendition]) -> Rendition | None:
    by_label = {r.label: r for r in renditions}
    for label in _RENDITION_PREFERENCE:
        if label in by_label:
            return by_label[label]
    return renditions[0] if renditions else None


class PlaybackService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def issue_token(self, asset: MediaAsset, viewer_user_id: int) -> tuple[str, PlaybackToken]:
        if asset.status != AssetStatus.READY or asset.archived_at is not None:
            raise BadRequestError("This media asset is not available for playback.", code="MEDIA_ASSET_NOT_READY")

        raw_token = generate_secure_token()
        token = PlaybackToken(
            public_id=new_public_id(),
            media_asset_id=asset.id,
            token_hash=hash_token(raw_token),
            issued_to=viewer_user_id,
            expires_at=utcnow() + timedelta(minutes=self.settings.PLAYBACK_TOKEN_EXPIRE_MINUTES),
        )
        self.db.add(token)
        await commit_or_conflict(self.db)
        return raw_token, token

    async def resolve(self, raw_token: str) -> str:
        """Validate the opaque token and return a freshly presigned, short-lived S3 GET URL."""
        token = (
            await self.db.execute(
                select(PlaybackToken)
                .where(PlaybackToken.token_hash == hash_token(raw_token))
                .options(selectinload(PlaybackToken.media_asset).selectinload(MediaAsset.renditions))
            )
        ).scalar_one_or_none()
        if token is None:
            raise NotFoundError("This playback link is invalid.", code="PLAYBACK_TOKEN_NOT_FOUND")
        if token.revoked_at is not None or token.expires_at <= utcnow():
            raise NotFoundError("This playback link has expired.", code="PLAYBACK_TOKEN_EXPIRED")

        asset = token.media_asset
        if asset.status != AssetStatus.READY or asset.archived_at is not None:
            raise NotFoundError("This media is no longer available.", code="MEDIA_ASSET_NOT_READY")

        rendition = _best_rendition(asset.renditions)
        storage_target = rendition.storage_key if rendition else asset.storage_key
        if storage_target and (storage_target.startswith("http://") or storage_target.startswith("https://") or storage_target.startswith("/")):
            return storage_target
        if rendition is None:
            raise NotFoundError("This media is no longer available.", code="MEDIA_ASSET_NOT_READY")
        if asset.kind == AssetKind.DOCUMENT:
            # shown inside the course player, not downloaded
            safe_name = "".join(c for c in asset.original_filename if c.isalnum() or c in " ._-")[:120] or "document.pdf"
            return await s3.presign_get(
                self.settings,
                rendition.storage_key,
                expires_seconds=self.settings.S3_PLAYBACK_URL_EXPIRES_SECONDS,
                content_type="application/pdf",
                disposition=f'inline; filename="{safe_name}"',
            )
        return await s3.presign_get(
            self.settings, rendition.storage_key, expires_seconds=self.settings.S3_PLAYBACK_URL_EXPIRES_SECONDS
        )
