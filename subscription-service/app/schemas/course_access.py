from lms_common.envelopes import ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, Timestamp


class CourseAccessOut(ResponseSchema):
    access_id: PublicIdOut = Field(validation_alias="public_id")
    course_id: PublicIdOut
    starts_at: Timestamp
    ends_at: Timestamp
    status: str = Field(description="active, or expired (buy again to re-open it)")


class CourseAccessListResponse(SuccessResponse):
    course_access: list[CourseAccessOut]
