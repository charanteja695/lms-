from lms_common.envelopes import SuccessResponse
from pydantic import BaseModel

from app.schemas.types import Timestamp


class PlaybackTokenOut(BaseModel):
    token: str
    expires_at: Timestamp
    playback_url: str


class PlaybackTokenResponse(SuccessResponse):
    playback: PlaybackTokenOut
