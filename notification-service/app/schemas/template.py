from lms_common.envelopes import RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.domain.enums import Channel
from app.schemas.types import Timestamp, multiline_text, text

TemplateSubject = text(300, examples=["You are enrolled in ${course_title}"])
TemplateBody = multiline_text(5_000, examples=["Hello ${first_name},\n\nYou are enrolled in ${course_title}."])


class TemplateOut(ResponseSchema):
    type: str = Field(validation_alias="type_key", examples=["enrollment.created"])
    category: str
    channel: Channel
    subject: str
    body: str
    default_subject: str
    default_body: str
    variables: list[str] = Field(description="Placeholders this template may use, as ${name}")
    is_customised: bool
    updated_at: Timestamp | None


class TemplateResponse(SuccessResponse):
    template: TemplateOut


class TemplateListResponse(SuccessResponse):
    templates: list[TemplateOut]


class TemplateUpdate(RequestSchema):
    subject: TemplateSubject  # type: ignore[valid-type]
    body: TemplateBody  # type: ignore[valid-type]
