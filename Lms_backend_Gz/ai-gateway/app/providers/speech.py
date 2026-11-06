"""STT/TTS routing contract — not built, same as the phase-6 proctoring AI-analyzer contract before it: needed
first by the phase-10 AI interviewer, so only the shape exists. Wiring a real provider means implementing this
interface (a ``TranscriptionProvider`` and a ``SpeechProvider``) and pointing ``Settings.STT_PROVIDER_URL`` /
``TTS_PROVIDER_URL`` at it; until then every call answers ``PROVIDER_NOT_CONFIGURED``.
"""

from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings
from app.core.exceptions import ProviderNotConfiguredError


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    text: str
    model: str
    seconds: float


@dataclass(frozen=True, slots=True)
class SpeechResult:
    audio: bytes
    content_type: str
    model: str


class TranscriptionProvider(Protocol):
    async def transcribe(self, audio: bytes, *, content_type: str) -> TranscriptionResult: ...


class SpeechProvider(Protocol):
    async def synthesize(self, text: str, *, voice: str | None) -> SpeechResult: ...


def require_stt_configured(settings: Settings) -> None:
    if not settings.STT_PROVIDER_URL:
        raise ProviderNotConfiguredError("No speech-to-text provider is configured yet.")


def require_tts_configured(settings: Settings) -> None:
    if not settings.TTS_PROVIDER_URL:
        raise ProviderNotConfiguredError("No text-to-speech provider is configured yet.")
