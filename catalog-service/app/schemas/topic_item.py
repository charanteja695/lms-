from typing import Self

from lms_common.envelopes import RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field, model_validator

from app.domain.enums import ItemType
from app.schemas.types import PublicIdOut, id_field, text

ItemTitle = text(200, min_length=3, examples=["Variables and let/const/var"])
MediaId = id_field("media_id", "1755000000000444")
ContentText = text(20_000, min_length=1)


class TopicItemCreate(RequestSchema):
    item_type: ItemType
    title: ItemTitle  # type: ignore[valid-type]
    required: bool = True
    media_id: MediaId | None = None  # type: ignore[valid-type]
    content_text: ContentText | None = None  # type: ignore[valid-type]

    @model_validator(mode="after")
    def _matches_item_type(self) -> Self:
        if self.item_type == ItemType.VIDEO and self.media_id is None:
            raise ValueError("media_id is required for a video item")
        if self.item_type in {ItemType.NOTES, ItemType.PRACTICE} and self.content_text is None:
            raise ValueError(f"content_text is required for a {self.item_type.value} item")
        return self


class TopicItemUpdate(RequestSchema):
    title: ItemTitle | None = None  # type: ignore[valid-type]
    required: bool | None = None
    media_id: MediaId | None = None  # type: ignore[valid-type]
    content_text: ContentText | None = None  # type: ignore[valid-type]


class TopicItemOut(ResponseSchema):
    topic_item_id: PublicIdOut = Field(validation_alias="public_id")
    item_type: str
    title: str
    position: int
    required: bool
    media_id: PublicIdOut | None = None
    media_ready: bool
    transcript_ready: bool
    duration_seconds: int | None = None
    content_text: str | None = None


class TopicItemResponse(SuccessResponse):
    topic_item: TopicItemOut
