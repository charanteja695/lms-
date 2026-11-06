from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.common import ListQuery
from app.schemas.types import PublicIdOut, Timestamp, id_field

EnrollStudentId = id_field("student_user_id", "1755000000005999")


class EnrollmentCreate(RequestSchema):
    student_user_id: EnrollStudentId  # type: ignore[valid-type]


class EnrollmentListQuery(ListQuery):
    batch_id: str | None = None


class EnrollmentOut(ResponseSchema):
    enrollment_id: PublicIdOut = Field(validation_alias="public_id")
    batch_id: PublicIdOut = Field(validation_alias="batch_public_id")
    student_user_id: PublicIdOut
    status: str
    enrolled_at: Timestamp
    withdrawn_at: Timestamp | None = None


class EnrollmentResponse(SuccessResponse):
    enrollment: EnrollmentOut


class EnrollmentListResponse(SuccessResponse):
    enrollments: list[EnrollmentOut]
    page_context: PageContext
