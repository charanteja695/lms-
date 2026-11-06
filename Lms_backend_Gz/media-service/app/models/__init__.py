"""Import every model here so Base.metadata (and Alembic) sees all tables."""

from app.db.base import Base
from app.models.caption import Caption
from app.models.media_asset import MediaAsset
from app.models.outbox_event import OutboxEvent
from app.models.playback_token import PlaybackToken
from app.models.rendition import Rendition
from app.models.transcript import Transcript

__all__ = [
    "Base",
    "Caption",
    "MediaAsset",
    "OutboxEvent",
    "PlaybackToken",
    "Rendition",
    "Transcript",
]
