"""Response envelopes every service's API uses (see lms-backend/README.md §4).

Success:  {"status": "success", "code": "SUCCESS", "message": "...", "<resource>": {...}}
List:     {... "<resources>": [...], "page_context": {...}}
Error:    {"status": "error", "code": "INVALID_DATA", "message": "...", "details": [...], "request_id": "..."}

Services build their own resource-specific response models on top of these bases; this module
only fixes the envelope shape so every service's API looks and behaves the same way.
"""

import math
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class RequestSchema(BaseModel):
    """Base for request bodies: unknown fields are rejected so clients cannot smuggle in
    e.g. a ``role`` or ``status`` the endpoint never asked for."""

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
    total_records: int = Field(examples=[57], description="Capped; see total_is_exact")
    total_is_exact: bool = Field(examples=[True], description="False when more records match than were counted")
    total_pages: int = Field(examples=[3])
    has_more_page: bool = Field(examples=[True])
    sort_column: str = Field(examples=["created_time"])
    sort_order: SortOrder

    @classmethod
    def build(
        cls, *, page: int, per_page: int, total: int, is_exact: bool, sort_column: str, sort_order: SortOrder
    ) -> Self:
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
