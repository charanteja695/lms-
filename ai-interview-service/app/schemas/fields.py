"""Field types shared by the request schemas."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, Field, HttpUrl, TypeAdapter
from pydantic_core import PydanticCustomError

from app.schemas.types import text

_URL = TypeAdapter(HttpUrl)


def _url(value: str) -> str:
    try:
        _URL.validate_python(value)
    except ValueError as exc:
        raise PydanticCustomError("INVALID_URL", "Use a full http(s) link") from exc
    if not value.lower().startswith(("http://", "https://")):
        raise PydanticCustomError("INVALID_URL", "Use a full http(s) link")
    return value


def _future(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise PydanticCustomError("INVALID_DATE", "Give the time with a timezone, for example 2026-12-31T18:30:00Z")
    return value.astimezone(UTC)


Url = Annotated[str, AfterValidator(_url), Field(max_length=300)]
AwareDatetime = Annotated[datetime, AfterValidator(_future)]
Skill = text(60)
SkillList = Annotated[list[Skill], Field(max_length=30)]  # type: ignore[valid-type]
Percent = Annotated[float, Field(ge=0, le=100)]
