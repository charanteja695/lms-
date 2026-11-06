# mypy: disable-error-code="valid-type"
# The pydantic plugin re-checks _LanguageFields' Any-returning field-type builders (text(), raw_text()) a second
# time when validating LanguageCreate/LanguageUpdate's narrowed overrides, at a synthesized location with no
# line number — a per-line `# type: ignore[valid-type]` (the usual idiom here, still used below for the primary
# occurrences) can't reach that second check, so it's disabled for the whole file instead.
from lms_common.envelopes import RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.domain.enums import LanguageKind
from app.schemas.types import Timestamp, raw_text, text

LanguageCode = text(30, examples=["python3"])
LanguageName = text(60, examples=["Python"])
LanguageVersion = text(30, examples=["3.12"])
FileName = text(60, examples=["main.py"])
EditorMode = text(30, examples=["python"])
StarterTemplate = raw_text(20_000)
CompilerOptions = text(200, examples=["-std=c++20 -O2"])


class LanguageOut(ResponseSchema):
    """What the editor needs to switch language: mode, file name and starter code (docs/PRODUCT.md §5.2)."""

    code: str
    name: str
    version: str
    kind: LanguageKind
    file_name: str
    editor_mode: str
    starter_template: str


class LanguageAdminOut(LanguageOut):
    engine_language_id: int | None
    compiler_options: str | None
    local_command: list[str] | None
    time_multiplier: float
    memory_multiplier: float
    enabled: bool
    sort_order: int
    updated_at: Timestamp


class LanguageListResponse(SuccessResponse):
    languages: list[LanguageOut]


class LanguageAdminListResponse(SuccessResponse):
    languages: list[LanguageAdminOut]


class LanguageResponse(SuccessResponse):
    language: LanguageAdminOut


class _LanguageFields(RequestSchema):
    name: LanguageName | None = None
    version: LanguageVersion | None = None
    kind: LanguageKind | None = None
    engine_language_id: int | None = Field(default=None, ge=1)
    compiler_options: CompilerOptions | None = None
    file_name: FileName | None = None
    editor_mode: EditorMode | None = None
    starter_template: StarterTemplate | None = None
    local_command: list[str] | None = Field(default=None, max_length=8)
    time_multiplier: float | None = Field(default=None, ge=0.1, le=20)
    memory_multiplier: float | None = Field(default=None, ge=0.1, le=20)
    enabled: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)


class LanguageCreate(_LanguageFields):
    code: LanguageCode
    name: LanguageName
    version: LanguageVersion
    file_name: FileName
    editor_mode: EditorMode


class LanguageUpdate(_LanguageFields):
    """Partial update: only the fields sent change."""
