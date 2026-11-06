from typing import Any

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.domain.enums import ConversationMode, Rating
from app.schemas.types import PublicIdOut, Timestamp, id_field, multiline_text, raw_text, text


class ConversationCreate(RequestSchema):
    mode: ConversationMode = ConversationMode.LEARNING
    course_id: id_field("Course", "1755000000001001") | None = None  # type: ignore[valid-type]


class MessageContextIn(RequestSchema):
    """What the student has open: the lesson or practice problem, the code they are working on, and whether they pressed
    the hint button."""

    item_id: id_field("Lesson", "1755000000001101") | None = None  # type: ignore[valid-type]
    code: raw_text(8_000) | None = None  # type: ignore[valid-type]
    language: text(30) | None = None  # type: ignore[valid-type]
    hint_request: bool = False


class MessageIn(RequestSchema):
    content: multiline_text(4_000)  # type: ignore[valid-type]
    context: MessageContextIn = Field(default_factory=MessageContextIn)
    stream: bool = False


class MessageOut(ResponseSchema):
    message_id: PublicIdOut = Field(validation_alias="public_id")
    role: str
    kind: str
    content: str
    citations: list[dict[str, Any]] | None
    confidence: float | None
    retrieval: str | None
    hint_level: int | None
    created_at: Timestamp


class ConversationOut(ResponseSchema):
    conversation_id: PublicIdOut = Field(validation_alias="public_id")
    mode: str
    course_id: PublicIdOut | None
    title: str
    status: str
    message_count: int
    last_message_at: Timestamp | None
    created_at: Timestamp


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut]


class EscalationBrief(ResponseSchema):
    escalation_id: PublicIdOut = Field(validation_alias="public_id")
    reason: str
    category: str
    status: str


class TurnOut(ResponseSchema):
    user_message: MessageOut
    assistant_message: MessageOut
    escalation: EscalationBrief | None = None


class ConversationResponse(SuccessResponse):
    conversation: ConversationOut


class ConversationDetailResponse(SuccessResponse):
    conversation: ConversationDetailOut


class ConversationListResponse(SuccessResponse):
    conversations: list[ConversationOut]
    page_context: PageContext


class TurnResponse(SuccessResponse):
    turn: TurnOut


class AvailabilityOut(ResponseSchema):
    enabled: bool
    reason: str | None = None
    attempt_id: PublicIdOut | None = None
    blocked_until: Timestamp | None = None


class AvailabilityResponse(SuccessResponse):
    availability: AvailabilityOut


class FeedbackIn(RequestSchema):
    rating: Rating
    comment: text(500) | None = None  # type: ignore[valid-type]


class FeedbackOut(ResponseSchema):
    message_id: PublicIdOut
    rating: str
    comment: str | None


class FeedbackResponse(SuccessResponse):
    feedback: FeedbackOut

