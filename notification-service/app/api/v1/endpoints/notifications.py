from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import CurrentAuth, DbSession, NotificationIdParam, WriteRateLimit
from app.api.responses import AUTHENTICATED, errors
from app.schemas.common import InboxQuery
from app.schemas.notification import (
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationOut,
    NotificationResponse,
    UnreadCountResponse,
)
from app.services.inbox_service import InboxService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListResponse, summary="List my notifications", responses=errors(*AUTHENTICATED))
async def list_notifications(query: Annotated[InboxQuery, Query()], auth: CurrentAuth, db: DbSession) -> NotificationListResponse:
    notifications, total, is_exact = await InboxService(db).list_for_user(auth.user_id, query)
    return NotificationListResponse(
        message="Notifications retrieved successfully.",
        notifications=[NotificationOut.model_validate(notification) for notification in notifications],
        page_context=PageContext.build(
            page=query.page,
            per_page=query.per_page,
            total=total,
            is_exact=is_exact,
            sort_column="created_time",
            sort_order=SortOrder(query.sort_order),
        ),
    )


@router.get("/unread-count", response_model=UnreadCountResponse, summary="Count my unread notifications", responses=errors(401, 429))
async def unread_count(auth: CurrentAuth, db: DbSession) -> UnreadCountResponse:
    return UnreadCountResponse(message="Unread count retrieved successfully.", unread_count=await InboxService(db).unread_count(auth.user_id))


@router.post(
    "/read-all",
    response_model=MarkAllReadResponse,
    summary="Mark all my notifications as read",
    responses=errors(401, 429),
    dependencies=[WriteRateLimit],
)
async def mark_all_read(auth: CurrentAuth, db: DbSession) -> MarkAllReadResponse:
    updated = await InboxService(db).mark_all_read(auth.user_id)
    return MarkAllReadResponse(message="Notifications marked as read.", updated_count=updated)


@router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark one notification as read",
    responses=errors(401, 404, 429),
    dependencies=[WriteRateLimit],
)
async def mark_read(notification_id: NotificationIdParam, auth: CurrentAuth, db: DbSession) -> NotificationResponse:
    notification = await InboxService(db).mark_read(auth.user_id, notification_id)
    return NotificationResponse(message="Notification marked as read.", notification=NotificationOut.model_validate(notification))
