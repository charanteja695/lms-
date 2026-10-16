from typing import Any

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field, field_validator

from app.domain.enums import CannedScope, Category, Priority, Queue, Source, TicketStatus
from app.schemas.types import PublicIdOut, Timestamp, id_field, multiline_text, text


# ---------------------------------------------------------------- requests
class AttachmentIn(RequestSchema):
    """A file already uploaded with an upload URL from `POST /attachments/upload-url`."""

    key: text(400)  # type: ignore[valid-type]
    filename: text(200)  # type: ignore[valid-type]


# How many a message may carry is ATTACHMENT_MAX_FILES (checked by the service); this only bounds the request.
Attachments = list[AttachmentIn]
_ATTACHMENTS: Any = Field(default_factory=list, max_length=20, description="Files uploaded beforehand; at most ATTACHMENT_MAX_FILES")


class AttachmentUploadRequest(RequestSchema):
    filename: text(200)  # type: ignore[valid-type]
    content_type: text(120)  # type: ignore[valid-type]
    size_bytes: int = Field(gt=0)


class TicketCreate(RequestSchema):
    subject: text(200, min_length=3)  # type: ignore[valid-type]
    description: multiline_text(8_000)  # type: ignore[valid-type]
    category: Category
    course_id: id_field("Course", "1755000000001001") | None = None  # type: ignore[valid-type]
    attachments: Attachments = _ATTACHMENTS


class InternalTicketCreate(RequestSchema):
    """Opened by another service on a person's behalf (the tutor's hand-off). ``Idempotency-Key`` makes a retry safe."""

    requester_user_id: id_field("User", "1755000000003001")  # type: ignore[valid-type]
    organization_id: id_field("Organization", "1755000000007003") | None = None  # type: ignore[valid-type]
    subject: text(200, min_length=3)  # type: ignore[valid-type]
    description: multiline_text(8_000)  # type: ignore[valid-type]
    category: Category = Category.LEARNING
    source: Source = Source.AI_TUTOR
    source_ref: text(80) | None = None  # type: ignore[valid-type]
    reason: text(40) | None = Field(default=None, description="Why the tutor handed over (low_confidence, user_requested, sensitive_topic); kept in the audit trail")  # type: ignore[valid-type]
    course_id: id_field("Course", "1755000000001001") | None = None  # type: ignore[valid-type]


class ReplyCreate(RequestSchema):
    body: multiline_text(8_000)  # type: ignore[valid-type]
    attachments: Attachments = _ATTACHMENTS


class AgentReplyCreate(RequestSchema):
    body: multiline_text(8_000)  # type: ignore[valid-type]
    internal: bool = Field(default=False, description="An internal note: never shown to the student, does not stop the SLA clock")
    then: TicketStatus | None = Field(default=None, description="Optionally move the ticket on: waiting_on_student or resolved")
    canned_reply_id: id_field("Canned reply", "1755000000009001") | None = None  # type: ignore[valid-type]
    attachments: Attachments = _ATTACHMENTS


class AssignRequest(RequestSchema):
    assignee_user_id: id_field("User", "1755000000003001")  # type: ignore[valid-type]


class TicketUpdate(RequestSchema):
    priority: Priority | None = None
    category: Category | None = None


class CsatRequest(RequestSchema):
    rating: int = Field(ge=1, le=5)
    comment: text(500) | None = None  # type: ignore[valid-type]


class CannedCreate(RequestSchema):
    scope: CannedScope = CannedScope.ORGANIZATION
    title: text(120)  # type: ignore[valid-type]
    body: multiline_text(4_000)  # type: ignore[valid-type]


class CannedUpdate(RequestSchema):
    title: text(120) | None = None  # type: ignore[valid-type]
    body: multiline_text(4_000) | None = None  # type: ignore[valid-type]
    active: bool | None = None


class SlaPolicyUpsert(RequestSchema):
    queue: Queue
    priority: Priority
    first_response_minutes: int = Field(ge=1, le=60 * 24 * 30)
    resolution_minutes: int = Field(ge=1, le=60 * 24 * 90)


# ---------------------------------------------------------------- responses
class AttachmentOut(ResponseSchema):
    filename: str
    content_type: str
    size_bytes: int


class MessageOut(ResponseSchema):
    message_id: PublicIdOut = Field(validation_alias="public_id")
    seq: int
    author_user_id: PublicIdOut | None
    author_role: str
    kind: str
    body: str
    attachments: list[AttachmentOut] = Field(default_factory=list, description="Download one with .../messages/{message_id}/attachments/{index}")
    created_at: Timestamp

    @field_validator("attachments", mode="before")
    @classmethod
    def _none_is_empty(cls, value: object) -> object:
        return value or []


class TicketOut(ResponseSchema):
    ticket_id: PublicIdOut = Field(validation_alias="public_id")
    subject: str
    category: str
    queue: str
    priority: str
    status: str
    source: str
    source_ref: str | None = None
    course_id: PublicIdOut | None
    requester_user_id: PublicIdOut
    organization_id: PublicIdOut | None
    assignee_user_id: PublicIdOut | None
    first_response_due_at: Timestamp | None
    resolution_due_at: Timestamp | None
    first_response_breached: bool
    resolution_breached: bool
    first_response_at: Timestamp | None
    resolved_at: Timestamp | None
    closed_at: Timestamp | None
    reopened_count: int
    csat_requested_at: Timestamp | None
    csat_rating: int | None
    created_at: Timestamp
    last_activity_at: Timestamp | None


class TranscriptMessageOut(ResponseSchema):
    message_id: str
    role: str
    kind: str
    content: str
    created_at: str


class TranscriptOut(ResponseSchema):
    """The tutor conversation behind a hand-off, as ai-tutor-service holds it (message ids let an agent promote an answer to the FAQ)."""

    conversation_id: str
    mode: str
    title: str
    messages: list[TranscriptMessageOut]


class TicketEventOut(ResponseSchema):
    event_type: str
    actor_user_id: PublicIdOut | None
    detail: dict[str, object] | None
    created_at: Timestamp


class TicketResponse(SuccessResponse):
    ticket: TicketOut


class TicketDetailResponse(SuccessResponse):
    ticket: TicketOut
    messages: list[MessageOut]
    requester_name: str | None = None
    assignee_name: str | None = None


class TicketPageResponse(SuccessResponse):
    tickets: list[TicketOut]
    page_context: PageContext


class MessageResponse(SuccessResponse):
    ticket: TicketOut
    reply: MessageOut


class EventsResponse(SuccessResponse):
    events: list[TicketEventOut]


class TranscriptResponse(SuccessResponse):
    transcript: TranscriptOut


class AssigneeOut(ResponseSchema):
    user_id: str
    name: str
    role: str


class AssigneesResponse(SuccessResponse):
    assignees: list[AssigneeOut]


class InternalTicketOut(ResponseSchema):
    ticket_id: PublicIdOut = Field(validation_alias="public_id")
    status: str
    queue: str


class InternalTicketResponse(SuccessResponse):
    ticket: InternalTicketOut


class CannedOut(ResponseSchema):
    canned_reply_id: PublicIdOut = Field(validation_alias="public_id")
    scope: str
    organization_id: PublicIdOut | None
    title: str
    body: str
    active: bool


class CannedResponse(SuccessResponse):
    canned_reply: CannedOut


class CannedListResponse(SuccessResponse):
    canned_replies: list[CannedOut]


class RenderedCanned(ResponseSchema):
    body: str


class RenderedCannedResponse(SuccessResponse):
    rendered: RenderedCanned


class SlaPolicyOut(ResponseSchema):
    queue: str
    priority: str
    first_response_minutes: int
    resolution_minutes: int
    is_default: bool


class SlaPoliciesResponse(SuccessResponse):
    policies: list[SlaPolicyOut]


class QueueSummaryOut(ResponseSchema):
    queue: str
    open: int
    assigned: int
    waiting_on_student: int
    unassigned: int
    breached: int
    oldest_unanswered_minutes: float | None


class SummaryResponse(SuccessResponse):
    queues: list[QueueSummaryOut]


class SlaReportOut(ResponseSchema):
    tickets: int
    resolved: int
    first_response_breached: int
    resolution_breached: int
    first_response_compliance: float | None
    resolution_compliance: float | None
    avg_first_response_minutes: float | None
    avg_resolution_minutes: float | None
    csat_responses: int
    csat_average: float | None
    reopened: int
    truncated: bool


class SlaReportResponse(SuccessResponse):
    report: SlaReportOut


class AttachmentUpload(ResponseSchema):
    key: str = Field(description="Send this back in a message's `attachments` once the upload has finished")
    upload: dict[str, Any] = Field(description="A presigned POST: `url` and the form `fields` to send with the file")
    expires_in: int


class AttachmentUploadResponse(SuccessResponse):
    attachment: AttachmentUpload


class AttachmentLink(ResponseSchema):
    filename: str
    url: str
    expires_in: int


class AttachmentLinkResponse(SuccessResponse):
    attachment: AttachmentLink
