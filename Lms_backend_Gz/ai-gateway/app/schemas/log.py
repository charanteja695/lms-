from typing import Any

from lms_common.envelopes import PageContext, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, Timestamp


class CallLogOut(ResponseSchema):
    call_id: PublicIdOut = Field(validation_alias="public_id")
    organization_id: PublicIdOut
    service: str
    user_id: PublicIdOut | None
    capability: str
    prompt_key: str | None
    prompt_version: int | None
    provider: str | None
    model: str | None
    request_redacted: dict[str, Any]
    response_preview: str | None
    prompt_tokens: int
    completion_tokens: int
    cost_cents: int
    latency_ms: int
    status: str
    error_code: str | None
    guardrail_flags: list[str]
    created_at: Timestamp


class CallLogListResponse(SuccessResponse):
    logs: list[CallLogOut]
    page_context: PageContext
