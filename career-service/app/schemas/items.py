"""The shape of a self-declared profile item, per kind. Verified items are built by the service, never from a request."""

import re
from typing import Annotated, Any

from lms_common.envelopes import RequestSchema
from pydantic import AfterValidator, Field, HttpUrl, TypeAdapter, ValidationError, model_validator
from pydantic_core import PydanticCustomError

from app.core.error_handlers import _validation_detail
from app.core.exceptions import ValidationFailedError
from app.domain.enums import SELF_KINDS, ItemKind
from app.schemas.types import multiline_text, text

_YEAR_MONTH = re.compile(r"^(19|20)[0-9]{2}-(0[1-9]|1[0-2])$")
_URL = TypeAdapter(HttpUrl)


def _year_month(value: str) -> str:
    if not _YEAR_MONTH.fullmatch(value):
        raise PydanticCustomError("INVALID_DATE", "Use YYYY-MM, for example 2024-06")
    return value


def _url(value: str) -> str:
    try:
        _URL.validate_python(value)
    except ValueError as exc:
        raise PydanticCustomError("INVALID_URL", "Use a full http(s) link") from exc
    if not value.lower().startswith(("http://", "https://")):
        raise PydanticCustomError("INVALID_URL", "Use a full http(s) link")
    return value


YearMonth = Annotated[str, AfterValidator(_year_month), Field(examples=["2024-06"])]
Url = Annotated[str, AfterValidator(_url), Field(max_length=300)]
Bullet = text(300)
Bullets = Annotated[list[Bullet], Field(max_length=8)]  # type: ignore[valid-type]


class _Dated(RequestSchema):
    start_date: YearMonth | None = None
    end_date: YearMonth | None = None

    @model_validator(mode="after")
    def _ordered(self) -> "_Dated":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise PydanticCustomError("INVALID_DATE_RANGE", "The end date is before the start date")
        return self


class EducationData(_Dated):
    institution: text(150)  # type: ignore[valid-type]
    degree: text(150)  # type: ignore[valid-type]
    field_of_study: text(150) | None = None  # type: ignore[valid-type]
    grade: text(40) | None = None  # type: ignore[valid-type]
    bullets: Bullets = Field(default_factory=list)


class ExperienceData(_Dated):
    company: text(150)  # type: ignore[valid-type]
    title: text(150)  # type: ignore[valid-type]
    location: text(120) | None = None  # type: ignore[valid-type]
    current: bool = False
    bullets: Bullets = Field(default_factory=list)

    @model_validator(mode="after")
    def _current_has_no_end(self) -> "ExperienceData":
        if self.current and self.end_date:
            raise PydanticCustomError("INVALID_DATE_RANGE", "A current role has no end date")
        return self


class ProjectData(_Dated):
    name: text(150)  # type: ignore[valid-type]
    url: Url | None = None
    technologies: Annotated[list[text(40)], Field(max_length=20)] = Field(default_factory=list)  # type: ignore[valid-type]
    description: multiline_text(600) | None = None  # type: ignore[valid-type]
    bullets: Bullets = Field(default_factory=list)


class SkillData(RequestSchema):
    name: text(60)  # type: ignore[valid-type]
    category: text(40) | None = None  # type: ignore[valid-type]


class AchievementData(RequestSchema):
    title: text(150)  # type: ignore[valid-type]
    date: YearMonth | None = None
    description: multiline_text(400) | None = None  # type: ignore[valid-type]


_MODELS: dict[ItemKind, type[RequestSchema]] = {
    ItemKind.EDUCATION: EducationData,
    ItemKind.EXPERIENCE: ExperienceData,
    ItemKind.PROJECT: ProjectData,
    ItemKind.SKILL: SkillData,
    ItemKind.ACHIEVEMENT: AchievementData,
}


def validate_item_data(kind: ItemKind, data: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalise ``data`` for a self-declared ``kind``; raises ValidationFailedError (422)."""
    if kind not in SELF_KINDS:
        raise ValueError(f"{kind} items are created by the platform")
    try:
        return _MODELS[kind].model_validate(data).model_dump(mode="json", exclude_none=True)
    except ValidationError as exc:
        raise ValidationFailedError(details=[_validation_detail({**e, "loc": ("body", "data", *e["loc"])}) for e in exc.errors()]) from exc
