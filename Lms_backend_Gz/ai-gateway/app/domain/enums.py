"""Enums stored as plain strings (not native DB enums) so new values don't need a type migration."""

from enum import StrEnum


class Capability(StrEnum):
    CHAT = "chat"
    EMBEDDING = "embedding"
    STT = "stt"
    TTS = "tts"


class PromptStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"  # the version served when a caller doesn't pin one; at most one per prompt
    RETIRED = "retired"


class CallStatus(StrEnum):
    OK = "ok"
    ERROR = "error"  # every configured provider failed
    BLOCKED = "blocked"  # moderation, a disallowed tool, or the org is suspended/disabled
    QUOTA_EXCEEDED = "quota_exceeded"


class ProviderName(StrEnum):
    ANTHROPIC = "anthropic"
    VOYAGE = "voyage"
