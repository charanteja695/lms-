from typing import Any, Literal

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, Timestamp, multiline_text, slug, text


class PromptCreateIn(RequestSchema):
    key: slug(80)  # type: ignore[valid-type]
    capability: Literal["chat", "embedding"] = "chat"
    owner_service: slug(60, examples=["ai-tutor-service"])  # type: ignore[valid-type]
    description: text(500, min_length=0) = ""  # type: ignore[valid-type]


class PromptOut(ResponseSchema):
    prompt_id: PublicIdOut = Field(validation_alias="public_id")
    key: str
    capability: str
    owner_service: str
    description: str
    created_by: PublicIdOut
    created_at: Timestamp


class PromptResponse(SuccessResponse):
    prompt: PromptOut


class PromptListResponse(SuccessResponse):
    prompts: list[PromptOut]
    page_context: PageContext


class PromptVersionCreateIn(RequestSchema):
    template: multiline_text(20_000)  # type: ignore[valid-type]
    variables: list[str] = Field(default_factory=list, max_length=50)
    allowed_tools: list[str] = Field(default_factory=list, max_length=20)
    model_params: dict[str, Any] = Field(default_factory=dict)


class PromptVersionOut(ResponseSchema):
    version_id: PublicIdOut = Field(validation_alias="public_id")
    version: int
    template: str
    variables: list[str]
    allowed_tools: list[str]
    model_params: dict[str, Any]
    status: str
    created_by: PublicIdOut
    activated_by: PublicIdOut | None
    retired_by: PublicIdOut | None
    created_at: Timestamp


class PromptVersionResponse(SuccessResponse):
    version: PromptVersionOut


class PromptDetailResponse(SuccessResponse):
    prompt: PromptOut
    versions: list[PromptVersionOut] = Field(description="Every version, newest first")
