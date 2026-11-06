from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse

from app.schemas.types import PublicIdOut, Timestamp, text

RejectReason = text(500, min_length=3, examples=["The topic test for module 2 is missing a pass mark"])


class RejectRequest(RequestSchema):
    reason: RejectReason  # type: ignore[valid-type]


class ReviewOut(ResponseSchema):
    action: str
    actor_user_id: PublicIdOut
    comment: str | None = None
    created_at: Timestamp


class ReviewListResponse(SuccessResponse):
    reviews: list[ReviewOut]
    page_context: PageContext
