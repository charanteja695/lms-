"""Enums stored as plain strings (not native DB enums) so new values don't need a type migration."""

from enum import StrEnum


class SessionStatus(StrEnum):
    """precheck -> ready -> active -> submitted -> closed (superseded / abandoned on the side)."""

    PRECHECK = "precheck"  # created; consent, system check and (strict) identity capture outstanding
    READY = "ready"  # pre-check passed; assessment-service may start the clock
    ACTIVE = "active"  # the attempt is running
    SUBMITTED = "submitted"  # the attempt ended; waiting for analysis and the integrity decision
    CLOSED = "closed"  # decided (automatically or by a person)
    SUPERSEDED = "superseded"  # a newer session for the same student and test replaced it
    ABANDONED = "abandoned"  # never started


class SnapshotKind(StrEnum):
    ID_PHOTO = "id_photo"
    FACE_ENROL = "face_enrol"
    PERIODIC = "periodic"
    SCREEN = "screen"
    AUDIO = "audio"
    LIVENESS = "liveness"  # before the test: the face turned left, right, up and down on request (one frame per pose)
    VIDEO = "video"  # during the test: a chunk of the continuous camera + microphone recording


LIVENESS_POSES = ("left", "right", "up", "down")


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"  # no analyzer configured, sampled out under load, or not needed


class CaseStatus(StrEnum):
    OPEN = "open"  # needs a human; nobody has picked it up
    UNDER_REVIEW = "under_review"  # a reviewer has claimed it
    DECIDED = "decided"  # cleared or reviewed_ok / invalidated; the student may appeal an invalidation once
    APPEALED = "appealed"  # an invalidation is being reconsidered by a different reviewer
    FINAL = "final"  # nothing more can change


class Decision(StrEnum):
    CLEAR = "clear"  # automatic: low risk, nothing critical
    REVIEWED_OK = "reviewed_ok"  # a person looked and found nothing
    INVALIDATED = "invalidated"  # a person confirmed the attempt is invalid


class AppealStatus(StrEnum):
    NONE = "none"
    REQUESTED = "requested"
    UPHELD = "upheld"  # the invalidation stands
    OVERTURNED = "overturned"  # the invalidation is withdrawn (reviewed_ok)


class DirectiveKind(StrEnum):
    WARN = "warn"
    PAUSE = "pause"
    RESUME = "resume"
    TERMINATE = "terminate"


class EventSource(StrEnum):
    CLIENT = "client"
    AI = "ai"
    SYSTEM = "system"
    STAFF = "staff"
