from lms_common.envelopes import RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.domain.enums import Category


class PreferenceOut(ResponseSchema):
    category: Category
    label: str
    email_enabled: bool
    email_editable: bool = Field(description="False: always emailed, the user cannot change it")


class PreferencesResponse(SuccessResponse):
    preferences: list[PreferenceOut]


class PreferenceChange(RequestSchema):
    category: Category
    email_enabled: bool


class PreferencesUpdate(RequestSchema):
    preferences: list[PreferenceChange] = Field(min_length=1, max_length=len(Category))
