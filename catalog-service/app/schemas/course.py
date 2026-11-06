from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.common import ListQuery
from app.schemas.types import PublicIdOut, Slug, Timestamp, id_field, text

CourseTitle = text(200, min_length=3, examples=["Full Stack Development with MERN"])
CourseSummary = text(500, min_length=10, examples=["Build and ship production web apps with MongoDB, Express, React and Node."])
ThumbnailMediaId = id_field("thumbnail_media_id", "1755000000000111")


class CourseCreate(RequestSchema):
    title: CourseTitle  # type: ignore[valid-type]
    slug: Slug
    summary: CourseSummary  # type: ignore[valid-type]
    thumbnail_media_id: ThumbnailMediaId | None = None  # type: ignore[valid-type]


class CourseUpdate(RequestSchema):
    title: CourseTitle | None = None  # type: ignore[valid-type]
    summary: CourseSummary | None = None  # type: ignore[valid-type]
    thumbnail_media_id: ThumbnailMediaId | None = None  # type: ignore[valid-type]


class CourseVersionSummary(ResponseSchema):
    version_id: PublicIdOut = Field(validation_alias="public_id")
    version_number: int
    status: str
    published_at: Timestamp | None = None


class CourseOut(ResponseSchema):
    course_id: PublicIdOut = Field(validation_alias="public_id")
    title: str
    slug: str
    summary: str
    thumbnail_media_id: PublicIdOut | None = None
    created_by: PublicIdOut
    archived_at: Timestamp | None = None
    created_at: Timestamp
    updated_at: Timestamp
    versions: list[CourseVersionSummary] = Field(default_factory=list)
    institutions_with_access: list[dict] = Field(default_factory=list)


class CourseResponse(SuccessResponse):
    course: CourseOut


class CourseListQuery(ListQuery):
    include_archived: bool = False
    published_only: bool = False


class CourseListResponse(SuccessResponse):
    courses: list[CourseOut]
    page_context: PageContext


class BulkDeleteRequest(RequestSchema):
    course_ids: list[str] = Field(default_factory=list)
    clear_all_active: bool = False


class BulkDeleteResponse(SuccessResponse):
    deleted_count: int
    affected_courses: list[str] = Field(default_factory=list)


class CatalogCleanupSummaryResponse(SuccessResponse):
    active_courses_count: int
    published_courses_count: int
    draft_courses_count: int
    total_modules_count: int
    total_chapters_count: int
