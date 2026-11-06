from typing import Literal

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.fields import Url
from app.schemas.types import PublicIdOut, Timestamp, multiline_text, text

CompanySize = Literal["1-10", "11-50", "51-200", "201-1000", "1000+"]


class EmployerProfileUpdate(RequestSchema):
    about: multiline_text(2_000) | None = None  # type: ignore[valid-type]
    website: Url | None = None
    industry: text(100) | None = None  # type: ignore[valid-type]
    company_size: CompanySize | None = None
    headquarters: text(120) | None = None  # type: ignore[valid-type]


class ReviewRequest(RequestSchema):
    approve: bool
    note: text(500) | None = Field(default=None, description="Required when rejecting: it is what the employer reads")  # type: ignore[valid-type]


class NoteRequest(RequestSchema):
    note: text(500)  # type: ignore[valid-type]


class EmployerOut(ResponseSchema):
    organization_id: PublicIdOut
    company_name: str
    about: str | None
    website: str | None
    industry: str | None
    company_size: str | None
    headquarters: str | None
    status: str
    review_note: str | None = None
    submitted_at: Timestamp | None = None
    reviewed_at: Timestamp | None = None
    open_jobs: int = 0


class EmployerResponse(SuccessResponse):
    employer: EmployerOut


class EmployerPage(SuccessResponse):
    employers: list[EmployerOut]
    page_context: PageContext
