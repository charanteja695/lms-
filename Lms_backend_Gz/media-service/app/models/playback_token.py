import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.media_asset import MediaAsset


class PlaybackToken(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """An opaque, short-lived token embedded in a ``<video src>``/player URL. Resolving it
    (``GET /playback/{token}``) issues a fresh presigned S3 GET URL, which lets us log who
    watched what and revoke access without touching S3 itself (see docs/PRODUCT.md §3.3)."""

    __tablename__ = "playback_tokens"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    media_asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("media_assets.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    issued_to: Mapped[int] = mapped_column(BigInteger, doc="public user_id of the viewer")
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]

    media_asset: Mapped["MediaAsset"] = relationship(lazy="raise")
