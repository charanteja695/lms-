from typing import Any, Literal

from lms_common.envelopes import RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, id_field, multiline_text, slug, text


class ChatMessageIn(RequestSchema):
    role: Literal["user", "assistant"]
    content: multiline_text(20_000)  # type: ignore[valid-type]


class CompletionIn(RequestSchema):
    organization_id: id_field("Organization", "1755000000007003")  # type: ignore[valid-type]
    service: slug(60, examples=["ai-tutor-service"])  # type: ignore[valid-type]  # the calling service's own name
    user_id: id_field("User", "1755000000007101") | None = None  # type: ignore[valid-type]
    prompt_key: slug(80)  # type: ignore[valid-type]
    prompt_version: int | None = Field(None, ge=1, description="Pin a specific version; omit to use the active one.")
    variables: dict[str, text(2_000)] = Field(default_factory=dict, max_length=50)  # type: ignore[valid-type]
    messages: list[ChatMessageIn] = Field(min_length=1, max_length=64)
    tools: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    max_tokens: int | None = Field(None, ge=1, le=100_000)
    temperature: float | None = Field(None, ge=0, le=2)
    model_hint: str | None = Field(None, max_length=60, description="Override the routed model; the provider is still chosen by app/providers/router.py.")
    stream: bool = False


class CompletionOut(ResponseSchema):
    call_id: PublicIdOut
    status: Literal["ok", "blocked", "error"]
    content: str
    model: str | None
    provider: str | None
    prompt_tokens: int
    completion_tokens: int
    cost_cents: int
    guardrail_flags: list[str]
    stop_reason: str | None
    prompt_version: int | None = None


class CompletionResponse(SuccessResponse):
    completion: CompletionOut
