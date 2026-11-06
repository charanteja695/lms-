"""List/filter query params. Domain-specific, so it stays per-service (see lms-backend/README.md);
the response envelope shapes themselves (SuccessResponse, PageContext, ...) come from lms_common."""

from typing import Self

from lms_common.envelopes import SortOrder
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import AssetKind, AssetStatus
from app.schemas.types import id_field

MAX_LIST_WINDOW = 10_000


class AssetListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_type: str | None = None
    context_id: id_field("context_id", "1755000000002123") | None = None  # type: ignore[valid-type]
    kind: AssetKind | None = None
    status: AssetStatus | None = None
    search: str | None = Field(default=None, max_length=100, description="Part of the file name")
    archived: bool = Field(default=False, description="true lists archived files instead of live ones")
    sort_order: SortOrder = SortOrder.DESC
    page: int = Field(default=1, ge=1, le=MAX_LIST_WINDOW)
    per_page: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def _within_window(self) -> Self:
        if self.page * self.per_page > MAX_LIST_WINDOW:
            raise ValueError(f"Lists show at most {MAX_LIST_WINDOW:,} records. Narrow the filters.")
        return self
