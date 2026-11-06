from lms_common.envelopes import RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, id_field, text

TopicTitle = text(200, min_length=3, examples=["Variables & Types"])
TopicTestId = id_field("topic_test_id", "1755000000000333")


class TopicCreate(RequestSchema):
    title: TopicTitle  # type: ignore[valid-type]
    pass_mark: int = Field(default=60, ge=0, le=100)


class TopicUpdate(RequestSchema):
    title: TopicTitle | None = None  # type: ignore[valid-type]
    pass_mark: int | None = Field(default=None, ge=0, le=100)
    topic_test_id: TopicTestId | None = None  # type: ignore[valid-type]


class TopicOut(ResponseSchema):
    topic_id: PublicIdOut = Field(validation_alias="public_id")
    title: str
    position: int
    pass_mark: int
    topic_test_id: PublicIdOut | None = None


class TopicResponse(SuccessResponse):
    topic: TopicOut
