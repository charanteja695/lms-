from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, Timestamp, text

CancelReason = text(500, min_length=3, examples=["Institution requested early termination"])


class CancelRequest(RequestSchema):
    reason: CancelReason  # type: ignore[valid-type]


class SubscriptionOut(ResponseSchema):
    subscription_id: PublicIdOut = Field(validation_alias="public_id")
    organization_id: PublicIdOut
    course_id: PublicIdOut
    seats_total: int
    seats_used: int
    starts_at: Timestamp
    ends_at: Timestamp
    status: str
    cancelled_at: Timestamp | None = None
    cancelled_reason: str | None = None
    created_at: Timestamp


class SubscriptionResponse(SuccessResponse):
    subscription: SubscriptionOut


class SubscriptionListResponse(SuccessResponse):
    subscriptions: list[SubscriptionOut]
    page_context: PageContext
