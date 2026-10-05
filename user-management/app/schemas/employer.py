"""Employers: hiring companies whose employer admins and recruiters use the job portal.

Employers share the organisation model with institutions (``organization_id``), so users, tokens and access
checks work the same way. Only the profile fields and member roles differ.
"""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from app.models.institution import Institution
from app.models.user import User
from app.permissions import capabilities
from app.permissions.roles import InstitutionStatus
from app.schemas.common import FilterQuery, ListQuery, PageContext, RequestSchema, ResponseSchema, SuccessResponse
from app.schemas.institution import ContactInput, ContactOut, ContactUpdate
from app.schemas.summaries import UserRef
from app.schemas.types import (
    CountryCode,
    InstitutionCode,
    PublicIdOut,
    Timestamp,
    TimeZoneName,
    UserId,
    Year,
    text,
)
from app.schemas.user import AddressInput, AddressOut

EmployerName = text(200, min_length=2, examples=["Acme Technologies Pvt Ltd"])
Industry = text(100, examples=["Information Technology"])
RegistrationNumber = text(50, examples=["U72900TG2015PTC098765"])


class EmployerCreate(RequestSchema):
    name: EmployerName  # type: ignore[valid-type]
    code: InstitutionCode = Field(description="Short unique code, stored in upper case", examples=["ACME-HYD"])
    industry: Industry | None = None  # type: ignore[valid-type]
    admin_user_id: UserId | None = Field(
        default=None,
        description="Owning admin (needs the careers.manage scope). Required for super admins; admins own what they create.",
    )
    contact: ContactInput
    address: AddressInput
    timezone: TimeZoneName | None = Field(default=None, description="Defaults to the service setting")
    registration_number: RegistrationNumber | None = Field(default=None, description="CIN, GSTIN or similar")  # type: ignore[valid-type]
    established_year: Year | None = None


class EmployerUpdate(RequestSchema):
    """Partial update. Only fields present in the body change."""

    name: EmployerName | None = None  # type: ignore[valid-type]
    code: InstitutionCode | None = None
    industry: Industry | None = None  # type: ignore[valid-type]
    admin_user_id: UserId | None = Field(default=None, description="Super admin only: transfer ownership")
    contact: ContactUpdate | None = None
    address: AddressInput | None = Field(default=None, description="Replaces the whole address")
    timezone: TimeZoneName | None = None
    registration_number: RegistrationNumber | None = None  # type: ignore[valid-type]
    established_year: Year | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Send at least one field to update")
        for name in ("name", "code", "admin_user_id", "contact", "address", "timezone"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class EmployerSortColumn(StrEnum):
    CREATED_TIME = "created_time"
    NAME = "name"
    CODE = "code"


class EmployerFilters(FilterQuery):
    status: InstitutionStatus | None = Field(default=None, description="'deleted' is available to super admins only")
    industry: text(100) | None = Field(default=None, description="Exact industry, case-insensitive")  # type: ignore[valid-type]
    admin_user_id: UserId | None = Field(default=None, description="Employers owned by this admin")
    country: CountryCode | None = None
    state: text(100) | None = None  # type: ignore[valid-type]
    city: text(100) | None = None  # type: ignore[valid-type]
    sort_column: EmployerSortColumn = EmployerSortColumn.CREATED_TIME


class EmployerListQuery(EmployerFilters, ListQuery):
    pass


class EmployerExportQuery(EmployerFilters):
    pass


class EmployerMemberCounts(ResponseSchema):
    employer_admins: int
    recruiters: int
    total: int

    @classmethod
    def of(cls, counts: dict[str, int]) -> Self:
        admins, recruiters = counts.get("employer_admin", 0), counts.get("recruiter", 0)
        return cls(employer_admins=admins, recruiters=recruiters, total=admins + recruiters)


class EmployerOut(ResponseSchema):
    organization_id: PublicIdOut
    name: str
    code: str
    industry: str | None
    status: InstitutionStatus
    status_reason: str | None
    contact: ContactOut
    address: AddressOut
    timezone: str
    registration_number: str | None
    established_year: int | None
    admin: UserRef
    member_counts: EmployerMemberCounts
    created_by: UserRef | None
    created_time: Timestamp
    modified_time: Timestamp
    deleted_time: Timestamp | None
    allowed_actions: list[str] = Field(
        default_factory=list, description="update, suspend, activate, revoke_sessions, delete, add_member, view_members"
    )

    @classmethod
    def from_model(cls, employer: Institution, counts: dict[str, int], actor: User | None = None) -> Self:
        admin = UserRef.of(employer.admin)
        assert admin is not None
        return cls(
            organization_id=employer.public_id,
            name=employer.name,
            code=employer.code,
            industry=employer.industry,
            status=InstitutionStatus(employer.status),
            status_reason=employer.status_reason,
            contact=ContactOut(
                email=employer.email,
                phone=employer.phone,
                alternate_phone=employer.alternate_phone,
                website=employer.website,
            ),
            address=AddressOut(
                line1=employer.address_line1,
                line2=employer.address_line2,
                city=employer.city,
                state=employer.state,
                postal_code=employer.postal_code,
                country=employer.country,
            ),
            timezone=employer.timezone,
            registration_number=employer.registration_number,
            established_year=employer.established_year,
            admin=admin,
            member_counts=EmployerMemberCounts.of(counts),
            created_by=UserRef.of(employer.created_by),
            created_time=employer.created_at,
            modified_time=employer.updated_at,
            deleted_time=employer.deleted_at,
            allowed_actions=capabilities.institution_actions(actor, employer) if actor else [],
        )


class EmployerListItem(ResponseSchema):
    organization_id: PublicIdOut
    name: str
    code: str
    industry: str | None
    status: InstitutionStatus
    city: str
    state: str
    country: str
    admin: UserRef
    member_counts: EmployerMemberCounts
    created_time: Timestamp
    allowed_actions: list[str] = Field(default_factory=list)

    @classmethod
    def from_model(cls, employer: Institution, counts: dict[str, int], actor: User | None = None) -> Self:
        admin = UserRef.of(employer.admin)
        assert admin is not None
        return cls(
            organization_id=employer.public_id,
            name=employer.name,
            code=employer.code,
            industry=employer.industry,
            status=InstitutionStatus(employer.status),
            city=employer.city,
            state=employer.state,
            country=employer.country,
            admin=admin,
            member_counts=EmployerMemberCounts.of(counts),
            created_time=employer.created_at,
            allowed_actions=capabilities.institution_actions(actor, employer) if actor else [],
        )


class EmployerResponse(SuccessResponse):
    employer: EmployerOut


class EmployerListResponse(SuccessResponse):
    employers: list[EmployerListItem]
    page_context: PageContext
