"""User requests and responses.

A user record is grouped into clear sections:

    account         email, username, password           (who they log in as)
    personal_info   names, gender, birth date, contact  (who they are)
    address         postal address                      (where they live)
    employment      admins, institution heads, staff    (their job)
    student         students only                       (admission + guardians)

Role-specific rules (e.g. students need an admission number) are enforced in
``app/validators/user_rules.py`` so every error for a request is reported at once.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, StrictBool, field_validator, model_validator

from app.domain.enums import EmploymentType, Gender, GuardianRelationship
from app.models.profiles import EmploymentProfile, StudentGuardian, StudentProfile, UserProfile
from app.models.user import User
from app.permissions import capabilities
from app.permissions.roles import AdminScope, Role, StatusChange, UserStatus
from app.schemas.common import FilterQuery, ListQuery, PageContext, RequestSchema, ResponseSchema, SuccessResponse
from app.schemas.summaries import InstitutionRef, UserRef
from app.schemas.types import (
    AdmissionNumber,
    CountryCode,
    DateOfBirth,
    EmailAddress,
    EmployeeCode,
    FirstName,
    FullName,
    LanguageCode,
    LastName,
    MiddleName,
    OrganizationId,
    Password,
    PastDate,
    PhoneNumber,
    PostalCode,
    PublicIdOut,
    Reason,
    Timestamp,
    TimeZoneName,
    UserId,
    Username,
    check_postal_code_for_country,
    text,
)

MAX_GUARDIANS = 4


class ManagedRole(StrEnum):
    """Roles that can be assigned through the API (super admins are created by CLI only)."""

    ADMIN = "admin"
    INSTITUTION_HEAD = "institution_head"
    STAFF = "staff"
    STUDENT = "student"
    EMPLOYER_ADMIN = "employer_admin"
    RECRUITER = "recruiter"


# ====================================================================== request sections


class AccountInput(RequestSchema):
    email: EmailAddress | None = Field(
        default=None,
        description="Required except for students. Students without email sign in with their username; "
        "without a password, a temporary one is generated and returned once.",
    )
    username: Username | None = Field(
        default=None, description="Optional. Generated from the name (e.g. priya.sharma) when omitted."
    )
    password: Password | None = Field(
        default=None,
        description="Optional initial password; the user must change it at first login. "
        "When omitted, an account set-up link is emailed instead (recommended), or a temporary password is "
        "generated for students without email.",
    )


class AccountUpdate(RequestSchema):
    email: EmailAddress | None = None
    username: Username | None = None

    @model_validator(mode="after")
    def _not_null(self) -> Self:
        _reject_explicit_nulls(self, ("username",))  # email may be cleared for students
        return self


class PersonalInfoInput(RequestSchema):
    first_name: FirstName
    middle_name: MiddleName | None = None
    last_name: LastName
    gender: Gender | None = None
    date_of_birth: DateOfBirth | None = Field(default=None, description="YYYY-MM-DD. Required for students.")
    phone: PhoneNumber | None = Field(
        default=None, description="Required for admins, institution heads and staff. Stored in E.164 format."
    )
    alternate_phone: PhoneNumber | None = None
    preferred_language: LanguageCode | None = Field(default=None, description="Defaults to the service setting (en)")
    timezone: TimeZoneName | None = Field(default=None, description="Defaults to the institution's time zone")

    @model_validator(mode="after")
    def _distinct_phones(self) -> Self:
        if self.phone and self.phone == self.alternate_phone:
            raise ValueError("alternate_phone must be different from phone")
        return self


class PersonalInfoUpdate(RequestSchema):
    first_name: FirstName | None = None
    middle_name: MiddleName | None = None
    last_name: LastName | None = None
    gender: Gender | None = None
    date_of_birth: DateOfBirth | None = None
    phone: PhoneNumber | None = None
    alternate_phone: PhoneNumber | None = None
    preferred_language: LanguageCode | None = None
    timezone: TimeZoneName | None = None

    @model_validator(mode="after")
    def _not_null(self) -> Self:
        _reject_explicit_nulls(self, ("first_name", "last_name", "preferred_language", "timezone"))
        return self


class AddressInput(RequestSchema):
    line1: text(255, examples=["Plot 42, Road No. 5"])  # type: ignore[valid-type]
    line2: text(255, examples=["Jubilee Hills"]) | None = None  # type: ignore[valid-type]
    city: text(100, examples=["Hyderabad"])  # type: ignore[valid-type]
    state: text(100, examples=["Telangana"])  # type: ignore[valid-type]
    postal_code: PostalCode
    country: CountryCode

    @model_validator(mode="after")
    def _postal_code_matches_country(self) -> Self:
        problem = check_postal_code_for_country(self.postal_code, self.country)
        if problem:
            raise ValueError(f"postal_code: {problem}")
        return self


class EmploymentInput(RequestSchema):
    employee_code: EmployeeCode | None = Field(
        default=None, description="Required for institution heads and staff. Unique within the institution."
    )
    designation: text(100, examples=["Mathematics Teacher"]) | None = None  # type: ignore[valid-type]
    department: text(100, examples=["Mathematics"]) | None = None  # type: ignore[valid-type]
    employment_type: EmploymentType | None = None
    date_of_joining: PastDate | None = None


class GuardianInput(RequestSchema):
    full_name: FullName
    relationship: GuardianRelationship
    phone: PhoneNumber
    email: EmailAddress | None = None
    occupation: text(100, examples=["Engineer"]) | None = None  # type: ignore[valid-type]
    is_primary: StrictBool = False


def _check_guardians(guardians: list[GuardianInput]) -> list[GuardianInput]:
    if not guardians:
        return guardians
    primaries = sum(g.is_primary for g in guardians)
    if len(guardians) == 1 and primaries == 0:
        guardians[0].is_primary = True
    elif primaries != 1:
        raise ValueError("Exactly one guardian must have is_primary set to true")
    phones = [g.phone for g in guardians]
    if len(set(phones)) != len(phones):
        raise ValueError("Each guardian must have a different phone number")
    return guardians


class StudentInput(RequestSchema):
    admission_number: AdmissionNumber = Field(description="Unique within the institution; never reused.")
    admission_date: PastDate | None = None
    program: text(100, examples=["B.Tech"]) | None = None  # type: ignore[valid-type]
    branch: text(100, examples=["Computer Science and Engineering"]) | None = None  # type: ignore[valid-type]
    year_of_study: int | None = Field(default=None, ge=1, le=10, examples=[3])
    section: text(20, examples=["A"]) | None = None  # type: ignore[valid-type]
    graduation_year: int | None = Field(default=None, ge=1950, le=2100, examples=[2027])
    cgpa: Decimal | None = Field(default=None, ge=0, le=10, max_digits=4, decimal_places=2, examples=["8.45"])
    guardians: list[GuardianInput] = Field(
        default_factory=list,
        max_length=MAX_GUARDIANS,
        description="Required (at least one) for students under 18. The first/only guardian is primary by default.",
    )

    _guardians = field_validator("guardians")(_check_guardians)


class StudentUpdate(RequestSchema):
    admission_number: AdmissionNumber | None = None
    admission_date: PastDate | None = None
    program: text(100, examples=["B.Tech"]) | None = None  # type: ignore[valid-type]
    branch: text(100, examples=["Computer Science and Engineering"]) | None = None  # type: ignore[valid-type]
    year_of_study: int | None = Field(default=None, ge=1, le=10, examples=[3])
    section: text(20, examples=["A"]) | None = None  # type: ignore[valid-type]
    graduation_year: int | None = Field(default=None, ge=1950, le=2100, examples=[2027])
    cgpa: Decimal | None = Field(default=None, ge=0, le=10, max_digits=4, decimal_places=2, examples=["8.45"])
    guardians: list[GuardianInput] | None = Field(
        default=None, max_length=MAX_GUARDIANS, description="When sent, replaces the full guardian list."
    )

    @field_validator("guardians")
    @classmethod
    def _valid_guardians(cls, value: list[GuardianInput] | None) -> list[GuardianInput] | None:
        return None if value is None else _check_guardians(value)

    @model_validator(mode="after")
    def _not_null(self) -> Self:
        _reject_explicit_nulls(self, ("admission_number", "guardians"))
        return self


def _reject_explicit_nulls(model: RequestSchema, fields: tuple[str, ...]) -> None:
    for name in fields:
        if name in model.model_fields_set and getattr(model, name) is None:
            raise ValueError(f"{name} cannot be null")


# ====================================================================== requests


class UserCreate(RequestSchema):
    role: ManagedRole
    organization_id: OrganizationId | None = Field(
        default=None,
        description="Organisation the user belongs to: an institution for institution_head, staff and student, "
        "an employer for employer_admin and recruiter (members may omit it: their own is used). Omit for admin.",
    )
    scopes: list[AdminScope] | None = Field(
        default=None, description="Admins only. Defaults to [accounts.manage]", examples=[["accounts.manage"]]
    )
    manager_user_id: UserId | None = Field(
        default=None,
        description="user_id of the person this user reports to (staff → head, student → staff). "
        "Defaults to the creator when the creator ranks higher in the same institution.",
    )
    account: AccountInput
    personal_info: PersonalInfoInput
    address: AddressInput | None = None
    employment: EmploymentInput | None = Field(default=None, description="For admin, institution_head, staff")
    student: StudentInput | None = Field(default=None, description="Required for student; not allowed otherwise")


class UserUpdate(RequestSchema):
    """Partial update. Only sections and fields present in the body change; send ``null`` to clear an optional value."""

    role: ManagedRole | None = Field(default=None, description="Only institution_head ↔ staff changes are allowed")
    organization_id: OrganizationId | None = Field(default=None, description="Move the user to another institution")
    manager_user_id: UserId | None = None
    scopes: list[AdminScope] | None = Field(default=None, description="Admins only. Replaces the full list")
    account: AccountUpdate | None = None
    personal_info: PersonalInfoUpdate | None = None
    address: AddressInput | None = Field(default=None, description="Replaces the whole address; null removes it")
    employment: EmploymentInput | None = None
    student: StudentUpdate | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Send at least one field to update")
        _reject_explicit_nulls(self, ("role", "account", "personal_info", "student"))
        return self


class MyContactUpdate(RequestSchema):
    phone: PhoneNumber | None = None
    alternate_phone: PhoneNumber | None = None
    preferred_language: LanguageCode | None = None
    timezone: TimeZoneName | None = None

    @model_validator(mode="after")
    def _not_null(self) -> Self:
        _reject_explicit_nulls(self, ("preferred_language", "timezone"))
        return self


class MyProfileUpdate(RequestSchema):
    """What users may change about themselves. Names, birth date and role are managed by their institution."""

    personal_info: MyContactUpdate | None = None
    address: AddressInput | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Send at least one field to update")
        return self


class StatusUpdate(RequestSchema):
    status: StatusChange
    reason: Reason | None = Field(default=None, description="Shown to administrators; recommended when suspending")


class UserSortColumn(StrEnum):
    CREATED_TIME = "created_time"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    EMAIL = "email"
    LAST_LOGIN_TIME = "last_login_time"


class UserFilters(FilterQuery):
    role: ManagedRole | None = None
    status: UserStatus | None = Field(default=None, description="'deleted' is available to super admins only")
    organization_id: OrganizationId | None = Field(default=None, description="Members of this institution")
    manager_user_id: UserId | None = Field(default=None, description="People who report to this user")
    created_by_user_id: UserId | None = Field(default=None, description="Accounts created by this user")
    gender: Gender | None = None
    department: text(100) | None = Field(default=None, description="Exact department name, case-insensitive")  # type: ignore[valid-type]
    employment_type: EmploymentType | None = None
    email_verified: bool | None = None
    program: text(100) | None = Field(default=None, description="Students: exact program, case-insensitive")  # type: ignore[valid-type]
    branch: text(100) | None = Field(default=None, description="Students: exact branch, case-insensitive")  # type: ignore[valid-type]
    year_of_study: int | None = Field(default=None, ge=1, le=10)
    section: text(20) | None = None  # type: ignore[valid-type]
    graduation_year: int | None = Field(default=None, ge=1950, le=2100)
    scope: AdminScope | None = Field(default=None, description="Admins holding this scope")
    sort_column: UserSortColumn = UserSortColumn.CREATED_TIME


class UserListQuery(UserFilters, ListQuery):
    pass


class UserExportQuery(UserFilters):
    pass


# ====================================================================== responses


class AccountOut(ResponseSchema):
    email: str | None
    username: str
    email_verified: bool
    must_change_password: bool
    last_login_time: Timestamp | None
    password_changed_time: Timestamp | None


class PersonalInfoOut(ResponseSchema):
    first_name: str
    middle_name: str | None
    last_name: str
    full_name: str
    gender: Gender | None
    date_of_birth: date | None
    phone: str | None
    alternate_phone: str | None
    preferred_language: str
    timezone: str


class AddressOut(ResponseSchema):
    line1: str
    line2: str | None
    city: str
    state: str
    postal_code: str
    country: str


class EmploymentOut(ResponseSchema):
    employee_code: str | None
    designation: str | None
    department: str | None
    employment_type: EmploymentType | None
    date_of_joining: date | None


class GuardianOut(ResponseSchema):
    full_name: str
    relationship: GuardianRelationship
    phone: str
    email: str | None
    occupation: str | None
    is_primary: bool


class StudentOut(ResponseSchema):
    admission_number: str
    admission_date: date | None
    program: str | None
    branch: str | None
    year_of_study: int | None
    section: str | None
    graduation_year: int | None
    cgpa: Decimal | None
    guardians: list[GuardianOut]


class UserOut(ResponseSchema):
    user_id: PublicIdOut
    role: Role
    status: UserStatus
    status_reason: str | None
    account: AccountOut
    personal_info: PersonalInfoOut
    address: AddressOut | None
    employment: EmploymentOut | None
    student: StudentOut | None
    institution: InstitutionRef | None
    manager: UserRef | None
    created_by: UserRef | None
    scopes: list[str] = Field(default_factory=list, description="Admins only")
    created_time: Timestamp
    modified_time: Timestamp
    deleted_time: Timestamp | None
    allowed_actions: list[str] = Field(
        default_factory=list,
        description="What you may do with this record: update, suspend, activate, revoke_sessions, reset_mfa, set_password, delete",
    )

    @classmethod
    def from_model(cls, user: User, actor: User | None = None) -> Self:
        """``user`` must be loaded with USER_DETAIL_OPTIONS. With ``actor``, ``allowed_actions`` is filled."""
        return cls(
            user_id=user.public_id,
            role=Role(user.role),
            status=UserStatus(user.status),
            status_reason=user.status_reason,
            account=account_out(user),
            personal_info=personal_info_out(user, user.profile),
            address=address_out(user.profile),
            employment=employment_out(user.employment),
            student=student_out(user.student, user.guardians),
            institution=InstitutionRef.of(user.institution),
            manager=UserRef.of(user.manager),
            created_by=UserRef.of(user.created_by),
            scopes=list(user.scope_list),
            created_time=user.created_at,
            modified_time=user.updated_at,
            deleted_time=user.deleted_at,
            allowed_actions=capabilities.user_actions(actor, user) if actor else [],
        )


class UserListItem(ResponseSchema):
    user_id: PublicIdOut
    role: Role
    status: UserStatus
    full_name: str
    email: str | None
    username: str
    phone: str | None
    employee_code: str | None
    admission_number: str | None
    branch: str | None = Field(description="Students only")
    year_of_study: int | None = Field(description="Students only")
    section: str | None = Field(description="Students only")
    graduation_year: int | None = Field(description="Students only")
    institution: InstitutionRef | None
    last_login_time: Timestamp | None
    created_time: Timestamp
    allowed_actions: list[str] = Field(
        default_factory=list,
        description="What you may do with this record: update, suspend, activate, revoke_sessions, reset_mfa, set_password, delete",
    )

    @classmethod
    def from_model(cls, user: User, actor: User | None = None) -> Self:
        """``user`` must be loaded with USER_LIST_OPTIONS."""
        return cls(
            user_id=user.public_id,
            role=Role(user.role),
            status=UserStatus(user.status),
            full_name=user.full_name,
            email=user.email,
            username=user.username,
            phone=user.phone,
            employee_code=user.employment.employee_code if user.employment else None,
            admission_number=user.student.admission_number if user.student else None,
            branch=user.student.branch if user.student else None,
            year_of_study=user.student.year_of_study if user.student else None,
            section=user.student.section if user.student else None,
            graduation_year=user.student.graduation_year if user.student else None,
            institution=InstitutionRef.of(user.institution),
            last_login_time=user.last_login_at,
            created_time=user.created_at,
            allowed_actions=capabilities.user_actions(actor, user) if actor else [],
        )


def account_out(user: User) -> AccountOut:
    return AccountOut(
        email=user.email,
        username=user.username,
        email_verified=user.email_verified_at is not None,
        must_change_password=user.must_change_password,
        last_login_time=user.last_login_at,
        password_changed_time=user.password_changed_at,
    )


def personal_info_out(user: User, profile: UserProfile | None) -> PersonalInfoOut:
    return PersonalInfoOut(
        first_name=user.first_name,
        middle_name=user.middle_name,
        last_name=user.last_name,
        full_name=user.full_name,
        gender=Gender(profile.gender) if profile and profile.gender else None,
        date_of_birth=profile.date_of_birth if profile else None,
        phone=user.phone,
        alternate_phone=profile.alternate_phone if profile else None,
        preferred_language=profile.preferred_language if profile else "en",
        timezone=profile.timezone if profile else "UTC",
    )


def address_out(profile: UserProfile | None) -> AddressOut | None:
    if profile is None or not profile.has_address:
        return None
    return AddressOut(
        line1=profile.address_line1 or "",
        line2=profile.address_line2,
        city=profile.city or "",
        state=profile.state or "",
        postal_code=profile.postal_code or "",
        country=profile.country or "",
    )


def employment_out(employment: EmploymentProfile | None) -> EmploymentOut | None:
    if employment is None:
        return None
    return EmploymentOut(
        employee_code=employment.employee_code,
        designation=employment.designation,
        department=employment.department,
        employment_type=EmploymentType(employment.employment_type) if employment.employment_type else None,
        date_of_joining=employment.date_of_joining,
    )


def student_out(student: StudentProfile | None, guardians: list[StudentGuardian]) -> StudentOut | None:
    if student is None:
        return None
    return StudentOut(
        admission_number=student.admission_number,
        admission_date=student.admission_date,
        program=student.program,
        branch=student.branch,
        year_of_study=student.year_of_study,
        section=student.section,
        graduation_year=student.graduation_year,
        cgpa=student.cgpa,
        guardians=[
            GuardianOut(
                full_name=g.full_name,
                relationship=GuardianRelationship(g.relationship_type),
                phone=g.phone,
                email=g.email,
                occupation=g.occupation,
                is_primary=g.is_primary,
            )
            for g in guardians
        ],
    )


# ====================================================================== envelopes


class UserResponse(SuccessResponse):
    user: UserOut


class CredentialsOut(ResponseSchema):
    delivery: Literal["email_link", "initial_password", "temporary_password"] = Field(
        description="email_link: set-up link emailed; initial_password: the password you chose; "
        "temporary_password: generated because the student has no email (shown once, share it securely)"
    )
    temporary_password: str | None = Field(
        default=None, description="Only for delivery=temporary_password; never shown again"
    )


class UserCreatedResponse(UserResponse):
    credentials: CredentialsOut


class SetPasswordRequest(RequestSchema):
    new_password: Password = Field(description="Temporary password; the user must change it at next sign-in")


class UserListResponse(SuccessResponse):
    users: list[UserListItem]
    page_context: PageContext


# ====================================================================== admins


class AdminCreate(RequestSchema):
    scopes: list[AdminScope] | None = Field(default=None, description="Defaults to [accounts.manage]")
    account: AccountInput
    personal_info: PersonalInfoInput
    address: AddressInput | None = None
    employment: EmploymentInput | None = None

    def to_user_create(self) -> UserCreate:
        return UserCreate.model_validate(
            {"role": ManagedRole.ADMIN, **self.model_dump(exclude_unset=True, mode="python")}
        )


class AdminUpdate(RequestSchema):
    scopes: list[AdminScope] | None = Field(default=None, description="Replaces the full list")
    account: AccountUpdate | None = None
    personal_info: PersonalInfoUpdate | None = None
    address: AddressInput | None = None
    employment: EmploymentInput | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Send at least one field to update")
        _reject_explicit_nulls(self, ("account", "personal_info", "scopes"))
        return self

    def to_user_update(self) -> UserUpdate:
        return UserUpdate.model_validate(self.model_dump(exclude_unset=True, mode="python"))


class AdminOut(UserOut):
    institution_count: int = Field(description="Active institutions owned by this admin")
    employer_count: int = Field(default=0, description="Active employers owned by this admin")


class AdminListItem(UserListItem):
    institution_count: int
    employer_count: int = 0
    scopes: list[str] = Field(default_factory=list)


class AdminFilters(FilterQuery):
    status: UserStatus | None = None
    scope: AdminScope | None = Field(default=None, description="Admins holding this scope")
    email_verified: bool | None = None
    sort_column: UserSortColumn = UserSortColumn.CREATED_TIME

    def as_user_filters(self, target: type[UserFilters]) -> UserFilters:
        return target.model_validate(self.model_dump(exclude_none=True))


class AdminListQuery(AdminFilters, ListQuery):
    pass


class AdminExportQuery(AdminFilters):
    pass


class AdminResponse(SuccessResponse):
    admin: AdminOut


class AdminCreatedResponse(AdminResponse):
    credentials: CredentialsOut


class AdminListResponse(SuccessResponse):
    admins: list[AdminListItem]
    page_context: PageContext
