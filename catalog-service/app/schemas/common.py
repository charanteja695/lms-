"""List/filter query params. Domain-specific, so it stays per-service (see lms-backend/README.md);
the response envelope shapes themselves (SuccessResponse, PageContext, ...) come from lms_common."""

from typing import Self

from lms_common.envelopes import RequestSchema, SortOrder
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.types import id_field, text

MAX_LIST_WINDOW = 10_000


class FilterQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search_text: text(100, min_length=2) | None = Field(  # type: ignore[valid-type]
        default=None, description="Case-insensitive 'contains' search over title, at least 2 characters"
    )
    sort_order: SortOrder = SortOrder.DESC


class ListQuery(FilterQuery):
    page: int = Field(default=1, ge=1, le=MAX_LIST_WINDOW, description="Page number, starting at 1")
    per_page: int = Field(default=20, ge=1, le=100, description="Records per page (max 100)")

    @model_validator(mode="after")
    def _within_window(self) -> Self:
        if self.page * self.per_page > MAX_LIST_WINDOW:
            raise ValueError(
                f"Lists show at most {MAX_LIST_WINDOW:,} records. Narrow the filters."
            )
        return self


class ReorderRequest(RequestSchema):
    """Every child's id, in the new order. Positions are reassigned 1..N to match."""

    ordered_ids: list[id_field("id", "1755000000000222")] = Field(min_length=1)  # type: ignore[valid-type]
