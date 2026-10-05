"""The full authoring tree for one course version: version -> rule -> modules -> topics -> items.
Composed from the per-resource ``*Out`` schemas so each stays usable on its own (e.g. a single
module response) as well as nested here for ``GET .../versions/{version_id}``.
"""

from lms_common.envelopes import ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.course_rule import CourseRuleOut
from app.schemas.module import ModuleOut
from app.schemas.topic import TopicOut
from app.schemas.topic_item import TopicItemOut
from app.schemas.types import PublicIdOut, Timestamp


class TopicDetail(TopicOut):
    items: list[TopicItemOut] = Field(default_factory=list)


class ModuleDetail(ModuleOut):
    topics: list[TopicDetail] = Field(default_factory=list)


class CourseVersionOut(ResponseSchema):
    version_id: PublicIdOut = Field(validation_alias="public_id")
    version_number: int
    status: str
    created_by: PublicIdOut
    submitted_at: Timestamp | None = None
    submitted_by: PublicIdOut | None = None
    reviewed_at: Timestamp | None = None
    reviewed_by: PublicIdOut | None = None
    reject_reason: str | None = None
    published_at: Timestamp | None = None
    retired_at: Timestamp | None = None
    created_at: Timestamp
    updated_at: Timestamp


class CourseVersionDetail(CourseVersionOut):
    rule: CourseRuleOut
    modules: list[ModuleDetail] = Field(default_factory=list)


class CourseVersionResponse(SuccessResponse):
    version: CourseVersionOut


class CourseVersionDetailResponse(SuccessResponse):
    version: CourseVersionDetail
