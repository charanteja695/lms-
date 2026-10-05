"""Scheduled reports (docs/PRODUCT.md §5.9 "Scheduled reports")."""

from typing import Any

from lms_common.envelopes import RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.domain.enums import Dashboard, ReportFormat, ReportFrequency
from app.schemas.types import PublicIdOut, Timestamp, text


class ReportFilters(RequestSchema):
    organization_id: str | None = Field(default=None, description="Required for the institution dashboard; optional elsewhere")
    employer_id: str | None = Field(default=None, description="Hiring dashboard only: scopes it to one employer's own jobs")


class ReportCreate(RequestSchema):
    name: text(160, min_length=3)  # type: ignore[valid-type]
    dashboard: Dashboard
    filters: ReportFilters = Field(default_factory=ReportFilters)
    frequency: ReportFrequency = ReportFrequency.WEEKLY
    format: ReportFormat = ReportFormat.CSV


class ReportOut(ResponseSchema):
    report_id: PublicIdOut
    name: str
    dashboard: str
    filters: dict[str, Any]
    format: str
    frequency: str
    next_run_at: Timestamp
    active: bool
    created_at: Timestamp


class ReportRunOut(ResponseSchema):
    run_id: PublicIdOut
    status: str
    period_start: str | None
    period_end: str | None
    row_count: int | None
    content_type: str | None
    error: str | None
    dashboard_snapshot: dict[str, Any] | None
    generated_at: Timestamp | None
    created_at: Timestamp


class ReportResponse(SuccessResponse):
    report: ReportOut


class ReportPage(SuccessResponse):
    reports: list[ReportOut]


class ReportRunResponse(SuccessResponse):
    run: ReportRunOut


class ReportRunPage(SuccessResponse):
    runs: list[ReportRunOut]
