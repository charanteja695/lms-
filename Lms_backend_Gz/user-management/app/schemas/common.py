"""Response envelopes shared by every endpoint.

Success:  {"status": "success", "code": "SUCCESS", "message": "...", "<resource>": {...}}
List:     {... "<resources>": [...], "page_context": {...}}
Error:    {"status": "error", "code": "INVALID_DATA", "message": "...", "details": [...], "request_id": "..."}
"""

import math
from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import SortOrder
from app.schemas.types import FilterDate, text


class RequestSchema(BaseModel):
    # Unknown fields are rejected so clients cannot smuggle in e.g. "role" or "status".
    model_config = ConfigDict(extra="forbid")


class ResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SuccessResponse(ResponseSchema):
    status: Literal["success"] = "success"
    code: Literal["SUCCESS"] = "SUCCESS"
    message: str = Field(examples=["Operation completed successfully."])


class PageContext(ResponseSchema):
    page: int = Field(examples=[1])
    per_page: int = Field(examples=[20])
    total_records: int = Field(examples=[57], description="Capped at 10,000; see total_is_exact")
    total_is_exact: bool = Field(examples=[True], description="False when more than 10,000 records match")
    total_pages: int = Field(examples=[3])
    has_more_page: bool = Field(examples=[True])
    sort_column: str = Field(examples=["created_time"])
    sort_order: SortOrder

    @classmethod
    def build(
        cls, *, page: int, per_page: int, total: int, is_exact: bool, sort_column: str, sort_order: SortOrder
    ) -> "PageContext":
        total_pages = math.ceil(total / per_page) if total else 0
        return cls(
            page=page,
            per_page=per_page,
            total_records=total,
            total_is_exact=is_exact,
            total_pages=total_pages,
            has_more_page=page < total_pages or (not is_exact and page == total_pages),
            sort_column=sort_column,
            sort_order=sort_order,
        )


class FilterQuery(BaseModel):
    """Filters shared by list and export endpoints. Unknown query parameters are rejected."""

    model_config = ConfigDict(extra="forbid")

    search_text: text(100, min_length=2) | None = Field(  # type: ignore[valid-type]
        default=None, description="Case-insensitive 'contains' search, at least 2 characters"
    )
    created_from: FilterDate | None = Field(default=None, description="Created on or after this date (YYYY-MM-DD, UTC)")
    created_to: FilterDate | None = Field(default=None, description="Created on or before this date (YYYY-MM-DD, UTC)")
    sort_order: SortOrder = SortOrder.DESC

    @model_validator(mode="after")
    def _valid_range(self) -> Self:
        if self.created_from and self.created_to and self.created_from > self.created_to:
            raise ValueError("created_from must be on or before created_to")
        return self


MAX_LIST_WINDOW = 10_000


class ListQuery(FilterQuery):
    page: int = Field(default=1, ge=1, le=MAX_LIST_WINDOW, description="Page number, starting at 1")
    per_page: int = Field(default=20, ge=1, le=100, description="Records per page (max 100)")

    @model_validator(mode="after")
    def _within_window(self) -> Self:
        if self.page * self.per_page > MAX_LIST_WINDOW:
            raise ValueError(
                f"Lists show at most {MAX_LIST_WINDOW:,} records. Narrow the filters or use the export endpoint."
            )
        return self


_ = date


class ErrorDetail(ResponseSchema):
    field: str | None = Field(examples=["personal_info.phone"])
    code: str = Field(examples=["INVALID_PHONE"])
    message: str = Field(examples=["Enter a valid phone number, e.g. +919876543210"])


class ErrorResponse(ResponseSchema):
    status: Literal["error"] = "error"
    code: str = Field(examples=["INVALID_DATA"])
    message: str = Field(examples=["Some fields are missing or invalid."])
    details: list[ErrorDetail] = Field(default_factory=list)
    request_id: str | None = Field(default=None, examples=["5f0c2b9ad4e84d6c9d1f3a7e2b8c4d10"])
