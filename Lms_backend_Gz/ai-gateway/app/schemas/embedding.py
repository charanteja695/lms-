from lms_common.envelopes import RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, id_field, raw_text, slug


class EmbeddingIn(RequestSchema):
    organization_id: id_field("Organization", "1755000000007003")  # type: ignore[valid-type]
    service: slug(60, examples=["ai-tutor-service"])  # type: ignore[valid-type]
    user_id: id_field("User", "1755000000007101") | None = None  # type: ignore[valid-type]
    texts: list[raw_text(8_000)] = Field(min_length=1, max_length=100)  # type: ignore[valid-type]
    model_hint: str | None = Field(None, max_length=60)


class EmbeddingOut(ResponseSchema):
    call_id: PublicIdOut
    vectors: list[list[float]]
    model: str | None
    provider: str | None
    tokens: int
    cost_cents: int


class EmbeddingResponse(SuccessResponse):
    embedding: EmbeddingOut
