from lms_common.envelopes import PageContext, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, Timestamp


class DeliveryOut(ResponseSchema):
    delivery_id: PublicIdOut = Field(validation_alias="public_id")
    notification_id: PublicIdOut = Field(validation_alias="notification_public_id")
    recipient_user_id: PublicIdOut
    channel: str
    status: str
    attempts: int
    last_error: str | None
    next_attempt_at: Timestamp
    sent_at: Timestamp | None
    created_at: Timestamp


class DeliveryResponse(SuccessResponse):
    delivery: DeliveryOut


class DeliveryListResponse(SuccessResponse):
    deliveries: list[DeliveryOut]
    page_context: PageContext
