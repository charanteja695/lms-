"""Interview plans: the request bodies staff write them with, and what a plan looks like back."""

from typing import Annotated, Any

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.domain.enums import Difficulty, PlanKind
from app.schemas.fields import SkillList
from app.schemas.types import PublicIdOut, Timestamp, multiline_text, slug, text


class RoundIn(RequestSchema):
    type: str
    minutes: int = Field(ge=3, le=60)
    questions: Annotated[list[text(500)], Field(min_length=1, max_length=15)]  # type: ignore[valid-type]
    languages: Annotated[list[slug(20)], Field(max_length=10)] = Field(default_factory=list)  # type: ignore[valid-type]
    criteria: Annotated[list[str], Field(max_length=5)] = Field(default_factory=list, description="Defaults to the round type's usual criteria")


class PlanFields(RequestSchema):
    title: text(160, min_length=3)  # type: ignore[valid-type]
    role: text(120, min_length=2)  # type: ignore[valid-type]
    skills: SkillList = Field(default_factory=list)
    difficulty: Difficulty = Difficulty.MEDIUM
    duration_minutes: int = Field(ge=10, le=90)
    rounds: Annotated[list[RoundIn], Field(min_length=1, max_length=6)]
    criteria_weights: dict[str, float] | None = Field(default=None, description="Defaults to equal weight across the criteria the rounds use")
    instructions: multiline_text(2_000) | None = Field(default=None)  # type: ignore[valid-type]
    proctoring_level: str = Field(default="none", pattern=r"^(none|basic|strict)$")
    max_attempts: int = Field(default=1, ge=1, le=5)
    retake_cooldown_days: int = Field(default=30, ge=0, le=365)


class PlanCreate(PlanFields):
    kind: PlanKind


class PlanUpdate(RequestSchema):
    title: text(160, min_length=3) | None = None  # type: ignore[valid-type]
    role: text(120, min_length=2) | None = None  # type: ignore[valid-type]
    skills: SkillList | None = None
    difficulty: Difficulty | None = None
    duration_minutes: int | None = Field(default=None, ge=10, le=90)
    rounds: Annotated[list[RoundIn], Field(min_length=1, max_length=6)] | None = None
    criteria_weights: dict[str, float] | None = None
    instructions: multiline_text(2_000) | None = None  # type: ignore[valid-type]
    proctoring_level: str | None = Field(default=None, pattern=r"^(none|basic|strict)$")
    max_attempts: int | None = Field(default=None, ge=1, le=5)
    retake_cooldown_days: int | None = Field(default=None, ge=0, le=365)


class PlanOut(ResponseSchema):
    plan_id: PublicIdOut
    family_id: PublicIdOut
    version: int
    owner_org_id: PublicIdOut | None
    kind: str
    title: str
    role: str
    skills: list[str]
    difficulty: str
    duration_minutes: int
    rounds: list[dict[str, Any]]
    criteria_weights: dict[str, float]
    instructions: str | None
    proctoring_level: str
    max_attempts: int
    retake_cooldown_days: int
    status: str
    published_at: Timestamp | None
    created_at: Timestamp


class PlanResponse(SuccessResponse):
    plan: PlanOut


class PlanPage(SuccessResponse):
    plans: list[PlanOut]
    page_context: PageContext
