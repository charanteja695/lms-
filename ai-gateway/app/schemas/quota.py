from lms_common.envelopes import RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut


class QuotaSetIn(RequestSchema):
    monthly_token_limit: int | None = Field(None, ge=0, description="null resets to the platform default")
    monthly_request_limit: int | None = Field(None, ge=0)
    monthly_budget_cents: int | None = Field(None, ge=0)
    enabled: bool = True


class QuotaOut(ResponseSchema):
    organization_id: PublicIdOut
    monthly_token_limit: int
    monthly_request_limit: int
    monthly_budget_cents: int
    enabled: bool
    is_default: bool = Field(description="True when the org has no override row and these are the platform defaults")


class QuotaResponse(SuccessResponse):
    quota: QuotaOut


class UsageOut(ResponseSchema):
    organization_id: PublicIdOut
    period: str
    requests_used: int
    prompt_tokens_used: int
    completion_tokens_used: int
    cost_cents_used: int
    token_limit: int
    request_limit: int
    budget_cents: int


class UsageResponse(SuccessResponse):
    usage: UsageOut
