from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, Slug, Timestamp, id_field, text

PathTitle = text(200, min_length=3, examples=["Full-Stack Web Developer Track"])
PathDescription = text(1000, min_length=10)
LearningPathCourseId = id_field("course_id", "1755000000000123")


class LearningPathCreate(RequestSchema):
    title: PathTitle  # type: ignore[valid-type]
    slug: Slug
    description: PathDescription  # type: ignore[valid-type]


class LearningPathUpdate(RequestSchema):
    title: PathTitle | None = None  # type: ignore[valid-type]
    description: PathDescription | None = None  # type: ignore[valid-type]


class LearningPathItemOut(ResponseSchema):
    course_id: PublicIdOut = Field(validation_alias="course_public_id")
    position: int
    title: str
    slug: str


class LearningPathOut(ResponseSchema):
    learning_path_id: PublicIdOut = Field(validation_alias="public_id")
    title: str
    slug: str
    description: str
    status: str
    created_by: PublicIdOut
    published_at: Timestamp | None = None
    archived_at: Timestamp | None = None
    items: list[LearningPathItemOut] = Field(default_factory=list)


class LearningPathResponse(SuccessResponse):
    learning_path: LearningPathOut


class LearningPathListResponse(SuccessResponse):
    learning_paths: list[LearningPathOut]
    page_context: PageContext


class LearningPathItemAdd(RequestSchema):
    course_id: LearningPathCourseId  # type: ignore[valid-type]
