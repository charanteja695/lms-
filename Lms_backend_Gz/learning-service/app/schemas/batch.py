from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, Timestamp, id_field, text

BatchName = text(200, min_length=3, examples=["2026 Batch A"])
BatchCourseId = id_field("course_id", "1755000000003555")
BatchOrganizationId = id_field("organization_id", "1755000000004003")


class BatchCreate(RequestSchema):
    course_id: BatchCourseId  # type: ignore[valid-type]
    name: BatchName  # type: ignore[valid-type]
    organization_id: BatchOrganizationId | None = Field(  # type: ignore[valid-type]
        default=None, description="Required for accounts.manage; an institution head's own institution is used otherwise"
    )


class BatchOut(ResponseSchema):
    batch_id: PublicIdOut = Field(validation_alias="public_id")
    organization_id: PublicIdOut
    version_id: PublicIdOut
    course_id: PublicIdOut
    title: str = Field(description="The course's title, for display only")
    subscription_id: PublicIdOut
    name: str
    status: str
    created_by: PublicIdOut
    created_at: Timestamp


class BatchResponse(SuccessResponse):
    batch: BatchOut


class BatchListResponse(SuccessResponse):
    batches: list[BatchOut]
    page_context: PageContext
