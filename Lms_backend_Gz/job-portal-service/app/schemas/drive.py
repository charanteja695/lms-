from datetime import date
from typing import Any

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, Timestamp, id_field, text


class DriveCreate(RequestSchema):
    employer_id: id_field("Employer", "1755000000007004")  # type: ignore[valid-type]
    institution_id: id_field("Institution", "1755000000007001") | None = None  # type: ignore[valid-type]
    title: text(160, min_length=3)  # type: ignore[valid-type]
    description: text(1_000) | None = None  # type: ignore[valid-type]
    drive_date: date | None = None
    deadline_date: date | None = None
    status: str | None = None
    job_ids: list[str] | None = None


class DriveRespond(RequestSchema):
    accept: bool


class AttachJob(RequestSchema):
    job_id: id_field("Job", "1755000000060101")  # type: ignore[valid-type]


class DriveOut(ResponseSchema):
    drive_id: PublicIdOut = Field(validation_alias="public_id")
    institution_id: PublicIdOut = Field(validation_alias="organization_id")
    employer_id: PublicIdOut = Field(validation_alias="employer_org_id")
    company_name: str | None = None
    institution_name: str | None = None
    title: str
    description: str | None
    drive_date: date | None
    status: str
    created_at: Timestamp


class DriveResponse(SuccessResponse):
    drive: DriveOut
    summary: dict[str, Any] | None = None


class DrivePage(SuccessResponse):
    drives: list[DriveOut]
    page_context: PageContext
