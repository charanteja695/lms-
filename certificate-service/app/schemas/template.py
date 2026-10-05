from typing import Any

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.render.layout import PLACEHOLDERS
from app.schemas.types import PublicIdOut, Timestamp, id_field, multiline_text, text

CourseId = id_field("course_id", "1755000000001001")


class SignatoryIn(RequestSchema):
    name: text(80)  # type: ignore[valid-type]
    title: text(80) = ""  # type: ignore[valid-type]


class GradeBandIn(RequestSchema):
    min_percent: int = Field(ge=0, le=100)
    label: text(60)  # type: ignore[valid-type]


class TemplateCreate(RequestSchema):
    """``body_text`` and ``footer_text`` may use these placeholders: """ + ", ".join("{" + p + "}" for p in sorted(PLACEHOLDERS))

    name: text(120)  # type: ignore[valid-type]
    course_id: CourseId | None = Field(default=None, description="Empty: the platform default for courses without their own")  # type: ignore[valid-type]
    title_text: text(120) = "Certificate of Completion"  # type: ignore[valid-type]
    body_text: multiline_text(1_000) | None = None  # type: ignore[valid-type]
    footer_text: text(300) | None = None  # type: ignore[valid-type]
    accent_color: str = "#1F4E79"
    signatories: list[SignatoryIn] = Field(default_factory=list, max_length=3)
    grade_bands: list[GradeBandIn] | None = Field(default=None, max_length=8)


class TemplateUpdate(RequestSchema):
    name: text(120) | None = None  # type: ignore[valid-type]
    title_text: text(120) | None = None  # type: ignore[valid-type]
    body_text: multiline_text(1_000) | None = None  # type: ignore[valid-type]
    footer_text: text(300) | None = None  # type: ignore[valid-type]
    accent_color: str | None = None
    signatories: list[SignatoryIn] | None = Field(default=None, max_length=3)
    grade_bands: list[GradeBandIn] | None = Field(default=None, max_length=8)


class TemplateOut(ResponseSchema):
    template_id: PublicIdOut = Field(validation_alias="public_id")
    course_id: PublicIdOut | None
    name: str
    status: str
    title_text: str
    body_text: str
    footer_text: str | None
    accent_color: str
    signatories: list[dict[str, Any]]
    grade_bands: list[dict[str, Any]]
    created_by: PublicIdOut
    created_at: Timestamp
    updated_at: Timestamp
    activated_at: Timestamp | None


class TemplateResponse(SuccessResponse):
    template: TemplateOut


class TemplateListResponse(SuccessResponse):
    templates: list[TemplateOut]
    page_context: PageContext
