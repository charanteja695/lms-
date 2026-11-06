from typing import Any

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.domain.enums import FaqScope, FaqStatus
from app.schemas.types import PublicIdOut, Timestamp, id_field, multiline_text, text


# ---------------------------------------------------------------- FAQ
class FaqCreate(RequestSchema):
    scope: FaqScope
    organization_id: id_field("Organization", "1755000000007003") | None = None  # type: ignore[valid-type]
    course_id: id_field("Course", "1755000000001001") | None = None  # type: ignore[valid-type]
    question: text(500)  # type: ignore[valid-type]
    answer: multiline_text(6_000)  # type: ignore[valid-type]


class FaqUpdate(RequestSchema):
    question: text(500) | None = None  # type: ignore[valid-type]
    answer: multiline_text(6_000) | None = None  # type: ignore[valid-type]


class FaqPromote(RequestSchema):
    """Turn a tutor answer into a draft FAQ entry: the student's question and the answer become the starting text, to be
    edited (in particular, stripped of anything personal) before it is published."""

    message_id: id_field("Message", "1755000000002001")  # type: ignore[valid-type]
    scope: FaqScope | None = Field(default=None, description="Defaults to the conversation's course, else its organization")


class FaqOut(ResponseSchema):
    faq_id: PublicIdOut = Field(validation_alias="public_id")
    scope: str
    organization_id: PublicIdOut | None
    course_id: PublicIdOut | None
    question: str
    answer: str
    status: FaqStatus
    helpful_count: int
    created_at: Timestamp


class FaqResponse(SuccessResponse):
    faq: FaqOut


class FaqListResponse(SuccessResponse):
    faqs: list[FaqOut]


class FaqPageResponse(SuccessResponse):
    faqs: list[FaqOut]
    page_context: PageContext


# ---------------------------------------------------------------- feedback summaries
class FeedbackSummaryOut(ResponseSchema):
    course_id: PublicIdOut
    up: int
    down: int
    down_rate: float | None


class FeedbackSummaryResponse(SuccessResponse):
    summary: FeedbackSummaryOut


class DownvotedOut(ResponseSchema):
    message_id: str
    question: str | None
    answer: str
    kind: str
    comment: str | None
    at: Timestamp


class DownvotedResponse(SuccessResponse):
    items: list[DownvotedOut]


# ---------------------------------------------------------------- evaluation
class EvalSetCreate(RequestSchema):
    course_id: id_field("Course", "1755000000001001")  # type: ignore[valid-type]
    name: text(120)  # type: ignore[valid-type]


class EvalCaseCreate(RequestSchema):
    question: text(500)  # type: ignore[valid-type]
    expected_item_ids: list[id_field("Lesson", "1755000000001101")] = Field(min_length=1, max_length=10)  # type: ignore[valid-type]


class EvalRunCreate(RequestSchema):
    top_k: int | None = Field(default=None, ge=1, le=20, description="hit@k: how many top lessons count; defaults to the tutor's own retrieval size")
    version_id: id_field("Course version", "1755000000001002") | None = None  # type: ignore[valid-type]


class EvalSetOut(ResponseSchema):
    eval_set_id: PublicIdOut = Field(validation_alias="public_id")
    course_id: PublicIdOut
    name: str
    created_at: Timestamp


class EvalCaseOut(ResponseSchema):
    case_id: PublicIdOut = Field(validation_alias="public_id")
    question: str
    expected_item_ids: list[str]


class EvalRunOut(ResponseSchema):
    run_id: PublicIdOut = Field(validation_alias="public_id")
    version_id: PublicIdOut
    method: str
    top_k: int
    case_count: int
    hits: int
    hit_rate: float
    mrr: float
    results: list[dict[str, Any]]
    created_at: Timestamp


class EvalSetResponse(SuccessResponse):
    eval_set: EvalSetOut


class EvalSetListResponse(SuccessResponse):
    eval_sets: list[EvalSetOut]


class EvalSetDetailResponse(SuccessResponse):
    eval_set: EvalSetOut
    cases: list[EvalCaseOut]
    runs: list[EvalRunOut]


class EvalCaseResponse(SuccessResponse):
    case: EvalCaseOut


class EvalRunResponse(SuccessResponse):
    run: EvalRunOut


# ---------------------------------------------------------------- index and escalations
class IndexVersionOut(ResponseSchema):
    version_id: PublicIdOut
    retired: bool
    chunks: int
    embedded_chunks: int
    job_status: str | None
    job_attempts: int
    last_error: str | None


class IndexStatusResponse(SuccessResponse):
    versions: list[IndexVersionOut]


class ReindexIn(RequestSchema):
    version_id: id_field("Course version", "1755000000001002")  # type: ignore[valid-type]


class EscalationOut(ResponseSchema):
    escalation_id: PublicIdOut = Field(validation_alias="public_id")
    conversation_id: PublicIdOut = Field(validation_alias="conversation_public_id")
    student_user_id: PublicIdOut = Field(validation_alias="user_id")
    organization_id: PublicIdOut | None
    course_id: PublicIdOut | None
    reason: str
    category: str
    status: str
    ticket_id: PublicIdOut | None
    attempts: int
    last_error: str | None
    created_at: Timestamp


class EscalationResponse(SuccessResponse):
    escalation: EscalationOut


class EscalationListResponse(SuccessResponse):
    escalations: list[EscalationOut]
    page_context: PageContext
