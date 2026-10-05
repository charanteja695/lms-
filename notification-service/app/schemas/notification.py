from typing import Any

from lms_common.envelopes import PageContext, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, Timestamp


class NotificationOut(ResponseSchema):
    notification_id: PublicIdOut = Field(validation_alias="public_id")
    type: str = Field(validation_alias="type_key", examples=["enrollment.created"])
    category: str = Field(examples=["enrollment"])
    title: str
    body: str
    data: dict[str, Any] = Field(description="Public ids to deep-link with, e.g. enrollment_id")
    read_at: Timestamp | None
    created_at: Timestamp


class NotificationResponse(SuccessResponse):
    notification: NotificationOut


class NotificationListResponse(SuccessResponse):
    notifications: list[NotificationOut]
    page_context: PageContext


class UnreadCountResponse(SuccessResponse):
    unread_count: int


class MarkAllReadResponse(SuccessResponse):
    updated_count: int
