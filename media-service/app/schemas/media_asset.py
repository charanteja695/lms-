from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, Timestamp, id_field, text

OriginalFilename = text(255, min_length=1, examples=["intro-to-variables.mp4"])
ContentType = text(100, min_length=3, examples=["video/mp4"])
ContextType = text(50, min_length=1, examples=["course_version"])
ContextId = id_field("context_id", "1755000000002123")


class UploadRequest(RequestSchema):
    original_filename: OriginalFilename  # type: ignore[valid-type]
    content_type: ContentType  # type: ignore[valid-type]
    byte_size: int = Field(gt=0, description="Declared size in bytes; verified against S3 after upload")
    context_type: ContextType | None = Field(default=None, description="Caller-defined tag, e.g. 'course_version'")  # type: ignore[valid-type]
    context_id: ContextId | None = None  # type: ignore[valid-type]


class UploadFields(ResponseSchema):
    url: str
    fields: dict[str, str]
    expires_at: Timestamp


class RenditionOut(ResponseSchema):
    label: str
    byte_size: int | None = None


class CaptionOut(ResponseSchema):
    language_code: str
    auto_generated: bool


class TranscriptOut(ResponseSchema):
    language_code: str


class MediaAssetOut(ResponseSchema):
    asset_id: PublicIdOut = Field(validation_alias="public_id")
    kind: str
    original_filename: str
    content_type: str
    byte_size: int | None = None
    status: str
    duration_seconds: int | None = None
    context_type: str | None = None
    context_id: PublicIdOut | None = None
    created_by: PublicIdOut
    failed_reason: str | None = None
    archived_at: Timestamp | None = None
    created_at: Timestamp
    updated_at: Timestamp
    renditions: list[RenditionOut] = Field(default_factory=list)
    captions: list[CaptionOut] = Field(default_factory=list)
    transcript: TranscriptOut | None = None


class UploadResponse(SuccessResponse):
    asset: MediaAssetOut
    upload: UploadFields


class MediaAssetResponse(SuccessResponse):
    asset: MediaAssetOut


class MediaAssetListResponse(SuccessResponse):
    assets: list[MediaAssetOut]
    page_context: PageContext
