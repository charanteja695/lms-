"""List/filter query params. Domain-specific, so it stays per-service (see lms-backend/README.md);
the response envelope shapes themselves (SuccessResponse, PageContext, ...) come from lms_common."""

from lms_common.envelopes import SortOrder
from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import DeliveryStatus

MAX_LIST_WINDOW = 10_000


class _PagedQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sort_order: SortOrder = SortOrder.DESC
    page: int = Field(default=1, ge=1, le=MAX_LIST_WINDOW)
    per_page: int = Field(default=20, ge=1, le=100)


class InboxQuery(_PagedQuery):
    unread: bool = Field(default=False, description="Only notifications not yet marked read")


class DeliveryQuery(_PagedQuery):
    status: DeliveryStatus | None = None
