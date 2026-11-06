from lms_common.envelopes import RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.domain.enums import Capability


class RouteEntryIn(RequestSchema):
    provider: str = Field(max_length=30)
    model: str = Field(max_length=60)


class ModelRouteSetIn(RequestSchema):
    providers: list[RouteEntryIn] = Field(min_length=1, max_length=5)


class RouteEntryOut(ResponseSchema):
    provider: str
    model: str


class ModelRoutesOut(ResponseSchema):
    chat: list[RouteEntryOut]
    embedding: list[RouteEntryOut]


class ModelRoutesResponse(SuccessResponse):
    models: ModelRoutesOut


class ModelRouteResponse(SuccessResponse):
    capability: Capability
    providers: list[RouteEntryOut]
