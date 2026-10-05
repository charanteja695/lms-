from lms_common.envelopes import RequestSchema, ResponseSchema
from pydantic import Field

from app.domain.enums import UnlockMode
from app.schemas.types import PublicIdOut, id_field

FinalTestId = id_field("final_test_id", "1755000000000555")


class CourseRuleUpdate(RequestSchema):
    unlock_mode: UnlockMode | None = None
    final_test_id: FinalTestId | None = None  # type: ignore[valid-type]
    final_pass_mark: int | None = Field(default=None, ge=0, le=100)
    final_test_attempts: int | None = Field(default=None, ge=1, le=10)
    final_test_cooldown_days: int | None = Field(default=None, ge=0, le=90)


class CourseRuleOut(ResponseSchema):
    unlock_mode: str
    final_test_id: PublicIdOut | None = None
    final_pass_mark: int
    final_test_attempts: int
    final_test_cooldown_days: int
