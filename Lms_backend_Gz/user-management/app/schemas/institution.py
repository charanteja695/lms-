from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from app.domain.enums import InstitutionType
from app.models.institution import Institution
from app.models.user import User
from app.permissions import capabilities
from app.permissions.roles import InstitutionStatus
from app.schemas.common import FilterQuery, ListQuery, PageContext, RequestSchema, ResponseSchema, SuccessResponse
from app.schemas.summaries import UserRef
from app.schemas.types import (
    CountryCode,
    EmailAddress,
    InstitutionCode,
    PhoneNumber,
    PublicIdOut,
    Timestamp,
    TimeZoneName,
    UserId,
    WebsiteUrl,
    Year,
    text,
)
from app.schemas.user import AddressInput, AddressOut

InstitutionName = text(200, min_length=3, examples=["Springfield High School"])
RegistrationNumber = text(50, examples=["TS-SCH-2004-1187"])
Affiliation = text(100, examples=["CBSE"])


class ContactInput(RequestSchema):
    email: EmailAddress
    phone: PhoneNumber
    alternate_phone: PhoneNumber | None = None
    website: WebsiteUrl | None = None

    @model_validator(mode="after")
    def _distinct_phones(self) -> Self:
        if self.alternate_phone and self.alternate_phone == self.phone:
            raise ValueError("alternate_phone must be different from phone")
        return self


class ContactUpdate(RequestSchema):
    email: EmailAddress | None = None
    phone: PhoneNumber | None = None
    alternate_phone: PhoneNumber | None = None
    website: WebsiteUrl | None = None

    @model_validator(mode="after")
    def _not_null(self) -> Self:
        for name in ("email", "phone"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class InstitutionCreate(RequestSchema):
    name: InstitutionName  # type: ignore[valid-type]
    code: InstitutionCode = Field(description="Short unique code, stored in upper case")
    type: InstitutionType
    admin_user_id: UserId | None = Field(
        default=None, description="Owning admin. Required for super admins; admins always own what they create."
    )
    contact: ContactInput
    address: AddressInput
    timezone: TimeZoneName | None = Field(default=None, description="Defaults to the service setting (Asia/Kolkata)")
    registration_number: RegistrationNumber | None = None  # type: ignore[valid-type]
    affiliation: Affiliation | None = Field(default=None, description="Board or university, e.g. CBSE")  # type: ignore[valid-type]
    established_year: Year | None = None


class InstitutionUpdate(RequestSchema):
    """Partial update. Only fields present in the body change."""

    name: InstitutionName | None = None  # type: ignore[valid-type]
    code: InstitutionCode | None = None
    type: InstitutionType | None = None
    admin_user_id: UserId | None = Field(default=None, description="Super admin only: transfer ownership")
    contact: ContactUpdate | None = None
    address: AddressInput | None = Field(default=None, description="Replaces the whole address")
    timezone: TimeZoneName | None = None
    registration_number: RegistrationNumber | None = None  # type: ignore[valid-type]
    affiliation: Affiliation | None = None  # type: ignore[valid-type]
    established_year: Year | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Send at least one field to update")
        for name in ("name", "code", "type", "admin_user_id", "contact", "address", "timezone"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class InstitutionSortColumn(StrEnum):
    CREATED_TIME = "created_time"
    NAME = "name"
    CODE = "code"


class InstitutionFilters(FilterQuery):
    status: InstitutionStatus | None = Field(default=None, description="'deleted' is available to super admins only")
    type: InstitutionType | None = None
    admin_user_id: UserId | None = Field(default=None, description="Institutions owned by this admin")
    country: CountryCode | None = None
    state: text(100) | None = Field(default=None, description="Exact state name, case-insensitive")  # type: ignore[valid-type]
    city: text(100) | None = Field(default=None, description="Exact city name, case-insensitive")  # type: ignore[valid-type]
    affiliation: text(100) | None = Field(default=None, description="Exact affiliation, e.g. CBSE")  # type: ignore[valid-type]
    sort_column: InstitutionSortColumn = InstitutionSortColumn.CREATED_TIME


class InstitutionListQuery(InstitutionFilters, ListQuery):
    pass


class InstitutionExportQuery(InstitutionFilters):
    pass


# ====================================================================== responses


class ContactOut(ResponseSchema):
    email: str
    phone: str
    alternate_phone: str | None
    website: str | None


class MemberCounts(ResponseSchema):
    institution_heads: int
    staff: int
    students: int
    total: int

    @classmethod
    def of(cls, counts: dict[str, int]) -> Self:
        heads, staff, students = counts.get("institution_head", 0), counts.get("staff", 0), counts.get("student", 0)
        return cls(institution_heads=heads, staff=staff, students=students, total=heads + staff + students)


class InstitutionOut(ResponseSchema):
    organization_id: PublicIdOut
    name: str
    code: str
    type: InstitutionType
    status: InstitutionStatus
    status_reason: str | None
    contact: ContactOut
    address: AddressOut
    timezone: str
    registration_number: str | None
    affiliation: str | None
    established_year: int | None
    admin: UserRef
    member_counts: MemberCounts
    created_by: UserRef | None
    created_time: Timestamp
    modified_time: Timestamp
    deleted_time: Timestamp | None
    allowed_actions: list[str] = Field(
        default_factory=list,
        description="What you may do: update, suspend, activate, revoke_sessions, delete, add_member, view_members",
    )

    @classmethod
    def from_model(cls, institution: Institution, counts: dict[str, int], actor: User | None = None) -> Self:
        admin = UserRef.of(institution.admin)
        assert admin is not None
        assert institution.institution_type is not None  # null only for the Employer org_type, never here
        return cls(
            organization_id=institution.public_id,
            name=institution.name,
            code=institution.code,
            type=InstitutionType(institution.institution_type),
            status=InstitutionStatus(institution.status),
            status_reason=institution.status_reason,
            contact=ContactOut(
                email=institution.email,
                phone=institution.phone,
                alternate_phone=institution.alternate_phone,
                website=institution.website,
            ),
            address=AddressOut(
                line1=institution.address_line1,
                line2=institution.address_line2,
                city=institution.city,
                state=institution.state,
                postal_code=institution.postal_code,
                country=institution.country,
            ),
            timezone=institution.timezone,
            registration_number=institution.registration_number,
            affiliation=institution.affiliation,
            established_year=institution.established_year,
            admin=admin,
            member_counts=MemberCounts.of(counts),
            created_by=UserRef.of(institution.created_by),
            created_time=institution.created_at,
            modified_time=institution.updated_at,
            deleted_time=institution.deleted_at,
            allowed_actions=capabilities.institution_actions(actor, institution) if actor else [],
        )


class InstitutionListItem(ResponseSchema):
    organization_id: PublicIdOut
    name: str
    code: str
    type: InstitutionType
    status: InstitutionStatus
    city: str
    state: str
    country: str
    admin: UserRef
    member_counts: MemberCounts
    created_time: Timestamp
    allowed_actions: list[str] = Field(
        default_factory=list,
        description="What you may do: update, suspend, activate, revoke_sessions, delete, add_member, view_members",
    )

    @classmethod
    def from_model(cls, institution: Institution, counts: dict[str, int], actor: User | None = None) -> Self:
        admin = UserRef.of(institution.admin)
        assert admin is not None
        assert institution.institution_type is not None  # null only for the Employer org_type, never here
        return cls(
            organization_id=institution.public_id,
            name=institution.name,
            code=institution.code,
            type=InstitutionType(institution.institution_type),
            status=InstitutionStatus(institution.status),
            city=institution.city,
            state=institution.state,
            country=institution.country,
            admin=admin,
            member_counts=MemberCounts.of(counts),
            created_time=institution.created_at,
            allowed_actions=capabilities.institution_actions(actor, institution) if actor else [],
        )


class InstitutionResponse(SuccessResponse):
    institution: InstitutionOut


class InstitutionListResponse(SuccessResponse):
    institutions: list[InstitutionListItem]
    page_context: PageContext
