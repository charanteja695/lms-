from lms_common.envelopes import RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, id_field, text

ModuleTitle = text(200, min_length=3, examples=["JavaScript Fundamentals"])
ModuleTestId = id_field("module_test_id", "1755000000000222")


class ModuleCreate(RequestSchema):
    title: ModuleTitle  # type: ignore[valid-type]
    description: str | None = None
    pass_mark: int = Field(default=60, ge=0, le=100)


class ModuleUpdate(RequestSchema):
    title: ModuleTitle | None = None  # type: ignore[valid-type]
    description: str | None = None
    pass_mark: int | None = Field(default=None, ge=0, le=100)
    module_test_id: ModuleTestId | None = None  # type: ignore[valid-type]


class ModuleOut(ResponseSchema):
    module_id: PublicIdOut = Field(validation_alias="public_id")
    title: str
    description: str | None = None
    position: int
    pass_mark: int
    module_test_id: PublicIdOut | None = None


class ModuleResponse(SuccessResponse):
    module: ModuleOut
