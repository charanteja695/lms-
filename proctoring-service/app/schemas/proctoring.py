from datetime import datetime
from typing import Any, Literal

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field, model_validator

from app.domain.enums import SnapshotKind
from app.schemas.types import PublicIdOut, Timestamp, id_field, multiline_text, text

TestId = id_field("test_id", "1755000000000555")


# ----------------------------------------------------------------------------- requests


class SessionCreate(RequestSchema):
    test_id: TestId  # type: ignore[valid-type]


class PrecheckIn(RequestSchema):
    """The system check the browser runs before the test (docs/PRODUCT.md §5.3 pre-check)."""

    consent: bool
    consent_version: text(20)  # type: ignore[valid-type]
    browser: text(120)  # type: ignore[valid-type]
    fullscreen_supported: bool
    camera: bool = False
    microphone: bool = False
    bandwidth_kbps: int = Field(default=0, ge=0)
    screen_share: bool = False
    device_fingerprint: text(128) | None = None  # type: ignore[valid-type]


class SnapshotUploadIn(RequestSchema):
    kind: SnapshotKind
    content_type: Literal["image/jpeg", "image/png", "image/webp", "audio/webm", "audio/ogg", "audio/mpeg"] = "image/jpeg"


class SnapshotRegisterIn(RequestSchema):
    kind: SnapshotKind
    key: text(300)  # type: ignore[valid-type]
    taken_at: datetime | None = None


class ClientEventIn(RequestSchema):
    type: text(30)  # type: ignore[valid-type]
    occurred_at: datetime | None = None
    detail: dict[str, Any] | None = None


class EventsIn(RequestSchema):
    events: list[ClientEventIn] = Field(min_length=1, max_length=100)


class HeartbeatIn(RequestSchema):
    device_fingerprint: text(128) | None = None  # type: ignore[valid-type]


class NoteIn(RequestSchema):
    message: text(500) | None = None  # type: ignore[valid-type]


class WarnIn(RequestSchema):
    message: text(500)  # type: ignore[valid-type]


class DecideIn(RequestSchema):
    decision: Literal["reviewed_ok", "invalidated"]
    note: multiline_text(2_000) | None = None  # type: ignore[valid-type]

    @model_validator(mode="after")
    def _invalidation_needs_a_reason(self) -> "DecideIn":
        if self.decision == "invalidated" and not self.note:
            raise ValueError("Invalidating an attempt needs a written reason")
        return self


class AppealIn(RequestSchema):
    reason: multiline_text(2_000)  # type: ignore[valid-type]


class AppealDecisionIn(RequestSchema):
    outcome: Literal["upheld", "overturned"]
    note: multiline_text(2_000)  # type: ignore[valid-type]


class FindingIn(RequestSchema):
    type: text(30)  # type: ignore[valid-type]
    confidence: float = Field(ge=0, le=1)
    detail: dict[str, Any] | None = None


class FindingsIn(RequestSchema):
    findings: list[FindingIn] = Field(max_length=20)


# ----------------------------------------------------------------------------- responses


class SessionOut(ResponseSchema):
    session_id: PublicIdOut = Field(validation_alias="public_id")
    test_id: PublicIdOut
    user_id: PublicIdOut
    organization_id: PublicIdOut | None
    attempt_id: PublicIdOut | None
    level: str
    status: str
    started_at: Timestamp | None
    ended_at: Timestamp | None
    last_heartbeat_at: Timestamp | None
    risk_score: int
    critical: bool
    terminated: bool
    created_at: Timestamp


class SessionDetailOut(SessionOut):
    risk_breakdown: dict[str, int]
    heartbeat_lost: bool
    consent_version: str | None
    ip_address: str | None


class Requirements(ResponseSchema):
    level: str
    consent_version: str
    needs: list[str]
    snapshot_interval_seconds: int
    heartbeat_interval_seconds: int
    min_bandwidth_kbps: int


class SessionResponse(SuccessResponse):
    session: SessionOut
    requirements: Requirements


class PrecheckResponse(SuccessResponse):
    ready: bool
    failures: list[dict[str, str]]
    session: SessionOut


class UploadOut(ResponseSchema):
    key: str
    upload: dict[str, Any]
    expires_in: int


class UploadResponse(SuccessResponse):
    file: UploadOut


class SnapshotOut(ResponseSchema):
    snapshot_id: PublicIdOut = Field(validation_alias="public_id")
    kind: str
    sequence: int
    taken_at: Timestamp
    analysis_status: str
    skip_reason: str | None
    flagged: bool
    findings: list[dict[str, Any]] | None


class SnapshotResponse(SuccessResponse):
    snapshot: SnapshotOut


class DirectiveOut(ResponseSchema):
    kind: str
    message: str | None
    created_at: Timestamp


class HeartbeatResponse(SuccessResponse):
    session_status: str  # not `status`: that is the envelope's own field
    risk_score: int
    directives: list[DirectiveOut]
    snapshot_interval_seconds: int
    server_time: Timestamp


class EventsResponse(SuccessResponse):
    accepted: int
    rejected: list[dict[str, str]]
    risk_score: int


class MonitorSessionResponse(SuccessResponse):
    session: SessionDetailOut
    events: list[dict[str, Any]]
    directives: list[DirectiveOut]


class SessionListResponse(SuccessResponse):
    sessions: list[SessionOut]
    page_context: PageContext


class CaseOut(ResponseSchema):
    case_id: PublicIdOut = Field(validation_alias="public_id")
    session_id: PublicIdOut = Field(validation_alias="session_public_id")
    attempt_id: PublicIdOut
    test_id: PublicIdOut
    user_id: PublicIdOut
    organization_id: PublicIdOut | None
    status: str
    severity: str
    risk_score: int
    reasons: list[str]
    assigned_to: PublicIdOut | None
    decision: str | None
    decided_by: PublicIdOut | None
    decided_at: Timestamp | None
    decision_note: str | None
    appeal_status: str
    appeal_reason: str | None
    appealed_at: Timestamp | None
    appeal_decided_by: PublicIdOut | None
    appeal_note: str | None
    overdue: bool = False
    can_appeal: bool = False
    created_at: Timestamp


class CaseDetailOut(CaseOut):
    report: dict[str, Any]
    snapshots: list[SnapshotOut]


class StudentCaseOut(ResponseSchema):
    """What the student sees of their own case: the outcome and how to appeal, never the other side's notes."""

    case_id: PublicIdOut = Field(validation_alias="public_id")
    attempt_id: PublicIdOut
    test_id: PublicIdOut
    status: str
    decision: str | None
    decision_note: str | None
    appeal_status: str
    can_appeal: bool = False
    created_at: Timestamp


class CaseResponse(SuccessResponse):
    case: CaseOut


class CaseDetailResponse(SuccessResponse):
    case: CaseDetailOut


class CaseListResponse(SuccessResponse):
    cases: list[CaseOut]
    page_context: PageContext


class StudentCasesResponse(SuccessResponse):
    cases: list[StudentCaseOut]


class StudentCaseResponse(SuccessResponse):
    case: StudentCaseOut


class MediaUrlResponse(SuccessResponse):
    url: str
    expires_in: int


class MediaAccessOut(ResponseSchema):
    snapshot_id: PublicIdOut
    session_id: PublicIdOut
    viewer_user_id: PublicIdOut
    reason: str
    created_at: Timestamp


class MediaAccessResponse(SuccessResponse):
    accesses: list[MediaAccessOut]
    page_context: PageContext


class QueueOut(ResponseSchema):
    analysis_pending: int
    sessions_awaiting_decision: int
    open_cases: int
    overdue_cases: int


class QueueResponse(SuccessResponse):
    queue: QueueOut
