from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, Timestamp, id_field, text

RequestCourseId = id_field("course_id", "1755000000003555")
DecisionReason = text(500, min_length=3, examples=["We only license this course for grades 9-12"])


class CourseRequestCreate(RequestSchema):
    course_id: RequestCourseId  # type: ignore[valid-type]
    requested_seats: int = Field(default=100, gt=0, le=100_000)
    requested_term_days: int = Field(default=365, gt=0, le=3_650)


class ApproveRequest(RequestSchema):
    """Defaults to what was requested; the admin may grant a different seat count or term."""

    seats: int | None = Field(default=None, gt=0, le=100_000)
    term_days: int | None = Field(default=None, gt=0, le=3_650)


class RejectRequest(RequestSchema):
    reason: DecisionReason  # type: ignore[valid-type]


class CourseRequestOut(ResponseSchema):
    course_request_id: PublicIdOut = Field(validation_alias="public_id")
    organization_id: PublicIdOut
    course_id: PublicIdOut
    requested_seats: int
    requested_term_days: int
    status: str
    requested_by: PublicIdOut
    decided_by: PublicIdOut | None = None
    decided_at: Timestamp | None = None
    decision_reason: str | None = None
    created_at: Timestamp
    course_name: str | None = None
    institution_name: str | None = None
    requester_name: str | None = None


class CourseRequestResponse(SuccessResponse):
    course_request: CourseRequestOut


class CourseRequestListResponse(SuccessResponse):
    course_requests: list[CourseRequestOut]
    page_context: PageContext
