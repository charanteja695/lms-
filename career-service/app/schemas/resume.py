from typing import Annotated, Any

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from app.domain.enums import ItemKind, SectionKey
from app.schemas.items import Bullets, Url
from app.schemas.types import PublicIdOut, Timestamp, id_field, multiline_text, text

# ---------------------------------------------------------------- the draft


class SummaryIn(RequestSchema):
    text: multiline_text(1_000) | None = None  # type: ignore[valid-type]
    visible: bool = True


class PersonalIn(RequestSchema):
    show_phone: bool = True
    show_location: bool = True
    show_links: bool = True


class SectionItemIn(RequestSchema):
    item_id: id_field("Profile item", "1755000000050001")  # type: ignore[valid-type]
    bullets: Bullets | None = Field(default=None, description="This resume's own wording for a self-declared item; ignored for verified items")


class SectionIn(RequestSchema):
    key: SectionKey
    title: text(60) | None = Field(default=None, description="Defaults to the standard heading; a non-standard heading lowers the ATS score")  # type: ignore[valid-type]
    visible: bool = True
    items: Annotated[list[SectionItemIn], Field(max_length=60)] = Field(default_factory=list)


class DraftIn(RequestSchema):
    summary: SummaryIn = Field(default_factory=SummaryIn)
    personal: PersonalIn = Field(default_factory=PersonalIn)
    sections: Annotated[list[SectionIn], Field(max_length=10)] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_sections(self) -> "DraftIn":
        keys = [s.key for s in self.sections]
        if len(set(keys)) != len(keys):
            raise PydanticCustomError("DUPLICATE_SECTION", "Each section may appear once")
        if SectionKey.SUMMARY in keys:
            raise PydanticCustomError("INVALID_SECTION", "The summary is set with `summary`, not as a section")
        return self


# ---------------------------------------------------------------- requests
class LinkIn(RequestSchema):
    label: text(40)  # type: ignore[valid-type]
    url: Url


class ProfileUpdate(RequestSchema):
    headline: text(160) | None = None  # type: ignore[valid-type]
    summary: multiline_text(1_000) | None = None  # type: ignore[valid-type]
    phone: text(30) | None = None  # type: ignore[valid-type]
    location: text(120) | None = None  # type: ignore[valid-type]
    links: Annotated[list[LinkIn], Field(max_length=6)] | None = None
    target_roles: Annotated[list[text(80)], Field(max_length=5)] | None = None  # type: ignore[valid-type]


class ItemCreate(RequestSchema):
    kind: ItemKind
    data: dict[str, Any]


class ItemUpdate(RequestSchema):
    data: dict[str, Any]


class ItemReorder(RequestSchema):
    kind: ItemKind
    item_ids: Annotated[list[id_field("Profile item", "1755000000050001")], Field(max_length=60)]  # type: ignore[valid-type]


class ResumeCreate(RequestSchema):
    title: text(120)  # type: ignore[valid-type]
    target_role: text(120) | None = None  # type: ignore[valid-type]
    template_key: text(30) | None = None  # type: ignore[valid-type]
    job_description: multiline_text(8_000) | None = None  # type: ignore[valid-type]
    blank: bool = Field(default=False, description="Start with no sections instead of everything in the profile")


class ResumeUpdate(RequestSchema):
    expected_revision: int = Field(ge=0, description="The draft_revision you loaded; a stale one is refused with 409 STALE_DRAFT")
    title: text(120) | None = None  # type: ignore[valid-type]
    target_role: text(120) | None = None  # type: ignore[valid-type]
    template_key: text(30) | None = None  # type: ignore[valid-type]
    job_description: multiline_text(8_000) | None = None  # type: ignore[valid-type]
    draft: DraftIn | None = None


class VersionCreate(RequestSchema):
    label: text(120) | None = None  # type: ignore[valid-type]
    note: multiline_text(500) | None = None  # type: ignore[valid-type]


class AtsRequest(RequestSchema):
    job_description: multiline_text(8_000) | None = Field(default=None, description="Defaults to the one saved on the resume")  # type: ignore[valid-type]


class RewriteRequest(RequestSchema):
    bullets: Annotated[list[text(300)], Field(min_length=1, max_length=8)]  # type: ignore[valid-type]
    context: text(200) | None = Field(default=None, description="For example the role or project the bullets belong to")  # type: ignore[valid-type]


class TextRequest(RequestSchema):
    text: multiline_text(2_000)  # type: ignore[valid-type]
    tone: text(20) | None = None  # type: ignore[valid-type]


class SummaryRequest(RequestSchema):
    tone: text(20) | None = Field(default=None, description="professional (default), warm or concise")  # type: ignore[valid-type]


class TailorRequest(RequestSchema):
    job_description: multiline_text(8_000) | None = None  # type: ignore[valid-type]
    include_summary: bool = Field(default=False, description="Also ask the AI for a summary that leans on the keywords you genuinely have")


class ShareRequest(RequestSchema):
    version_no: int | None = Field(default=None, ge=1, description="Defaults to a fresh snapshot of the current draft")
    expires_in_days: int | None = Field(default=None, ge=1, le=365)
    show_contact: bool = Field(default=False, description="Show email, phone and location on the public page (off by default)")


# ---------------------------------------------------------------- responses
class LinkOut(ResponseSchema):
    label: str
    url: str


class ProfileOut(ResponseSchema):
    headline: str | None
    summary: str | None
    phone: str | None
    location: str | None
    links: list[LinkOut]
    target_roles: list[str]
    revision: int


class PersonalOut(ResponseSchema):
    name: str
    email: str | None
    name_verified: bool = True


class ItemOut(ResponseSchema):
    item_id: PublicIdOut
    kind: str
    verified: bool
    label: str
    source: str
    active: bool
    data: dict[str, Any]
    derived: dict[str, Any]
    position: int
    inactive_reason: str | None = None


class ProfileResponse(SuccessResponse):
    profile: ProfileOut
    personal: PersonalOut
    items: list[ItemOut]


class ItemResponse(SuccessResponse):
    item: ItemOut


class ItemsResponse(SuccessResponse):
    items: list[ItemOut]


class TemplateOut(ResponseSchema):
    key: str
    name: str
    description: str
    ats_safe: bool


class TemplatesResponse(SuccessResponse):
    templates: list[TemplateOut]


class ResumeOut(ResponseSchema):
    resume_id: PublicIdOut = Field(validation_alias="public_id")
    title: str
    target_role: str | None
    template_key: str
    draft_revision: int
    latest_version_no: int
    shared: bool = False
    share_expires_at: Timestamp | None = None
    created_at: Timestamp
    updated_at: Timestamp


class ResumeDetail(SuccessResponse):
    resume: ResumeOut
    job_description: str | None
    draft: dict[str, Any]
    document: dict[str, Any]
    ats: dict[str, Any]


class ResumeResponse(SuccessResponse):
    resume: ResumeOut


class ResumePage(SuccessResponse):
    resumes: list[ResumeOut]
    page_context: PageContext


class VersionOut(ResponseSchema):
    version_no: int
    label: str | None
    source: str
    template_key: str
    ats_score: int | None
    note: str | None
    created_at: Timestamp


class VersionResponse(SuccessResponse):
    version: VersionOut


class VersionDetail(SuccessResponse):
    version: VersionOut
    document: dict[str, Any]


class VersionsResponse(SuccessResponse):
    versions: list[VersionOut]


class AtsResponse(SuccessResponse):
    ats: dict[str, Any]


class GrammarResponse(SuccessResponse):
    issues: list[dict[str, Any]]


class SuggestionResponse(SuccessResponse):
    suggestion: dict[str, Any]


class SuggestionsResponse(SuccessResponse):
    suggestions: list[dict[str, Any]]


class ShareOut(ResponseSchema):
    token: str
    url_path: str
    version_no: int
    expires_at: Timestamp | None
    show_contact: bool


class ShareResponse(SuccessResponse):
    share: ShareOut


class PublicResumeResponse(ResponseSchema):
    resume: dict[str, Any]


class SnapshotRequest(RequestSchema):
    user_id: id_field("User", "1755000000003001")  # type: ignore[valid-type]
    label: text(120)  # type: ignore[valid-type]
    note: multiline_text(500) | None = None  # type: ignore[valid-type]


class SnapshotResponse(SuccessResponse):
    resume_id: PublicIdOut
    user_id: PublicIdOut
    title: str
    target_role: str | None
    version_no: int
    template_key: str
    ats_score: int | None
    document: dict[str, Any]
