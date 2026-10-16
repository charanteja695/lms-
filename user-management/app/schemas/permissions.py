"""Capabilities of the signed-in person, so clients render from data instead of re-implementing rules."""

from typing import Literal

from pydantic import Field

from app.permissions.roles import Role
from app.schemas.common import ResponseSchema, SuccessResponse

Section = Literal[
    "dashboard",
    "admins",
    "institutions",
    "employers",
    "my_organization",
    "academics",
    "hierarchy",
    "users",
    "downloads",
    "audit_logs",
    "permissions",
    "profile",
    "security",
    # One per other backend service (docs/PRODUCT.md §6), gating that module's whole side-menu entry. Coarse only:
    # who sees the *student* vs *staff* vs *admin* view within a section is that service's own, finer-grained call.
    "catalog",
    "subscriptions",
    "learning",
    "code_execution",
    "assessments",
    "proctoring",
    "certificates",
    "ai_tutor",
    "support",
    "career",
    "job_portal",
    "ai_interview",
    "notifications",
    "analytics",
    "billing",
    "ai_gateway",
]


class UsersPermissionsOut(ResponseSchema):
    view_roles: list[Role] = Field(description="Roles whose users you can see (admins excluded; see admins.view)")
    create_roles: list[Role]
    can_import: bool
    can_export: bool
    filter_statuses: list[str] = Field(examples=[["active", "suspended"]])
    filter_by_institution: bool


class AdminsPermissionsOut(ResponseSchema):
    view: bool
    create: bool


class OrganizationsPermissionsOut(ResponseSchema):
    create: bool
    filter_statuses: list[str]
    filter_by_admin: bool
    reassign_admin: bool


class AcademicsPermissionsOut(ResponseSchema):
    view: bool = Field(description="Sees the institution's departments, programs and sections")
    manage: bool = Field(description="Creates and changes them, and places students in sections")


class AuditLogsPermissionsOut(ResponseSchema):
    view: bool


class PermissionsOut(ResponseSchema):
    role: Role
    organization_type: str | None = Field(description="institution or employer, for organisation members")
    scopes: list[str] = Field(description="Admin scopes of the signed-in person")
    permissions: list[str] = Field(
        description="Effective permissions (feature keys): role defaults + scopes + this person's grants − removals. Show buttons from these"
    )
    sections: list[Section] = Field(description="Menu sections to show, in display order")
    menu: list[str] = Field(
        description="Menu entries within those modules this person's role or scopes reach (feature level), in display order"
    )
    users: UsersPermissionsOut
    admins: AdminsPermissionsOut
    institutions: OrganizationsPermissionsOut
    employers: OrganizationsPermissionsOut
    admin_scopes: list[str] = Field(description="Scopes you can assign to admins (super admins only)")
    audit_logs: AuditLogsPermissionsOut
    academics: AcademicsPermissionsOut


class PermissionsResponse(SuccessResponse):
    permissions: PermissionsOut


class FormOrganizationOut(ResponseSchema):
    shown: bool
    type: str | None = Field(description="institution or employer")
    required: bool
    selectable: bool = Field(description="False when the organisation is fixed to yours")
    fixed: bool


class FormScopesOut(ResponseSchema):
    shown: bool
    options: list[str]
    default: list[str] = Field(description="Pre-select these when creating an admin")


class FormManagerOut(ResponseSchema):
    shown: bool
    role: Role | None = Field(description="Role the manager must have")
    defaults_to_you: bool


class FormSectionsOut(ResponseSchema):
    address: bool
    employment: bool
    student: bool
    guardians: bool


class FormGuardiansOut(ResponseSchema):
    max: int
    required_below_age: int


class FormInitialPasswordOut(ResponseSchema):
    allowed: bool
    min_length: int
    generated_without_email: bool = Field(description="A temporary password is generated when email is left empty")


class FormDefaultsOut(ResponseSchema):
    language: str
    timezone: str
    country: str


class UserFormOptionsOut(ResponseSchema):
    roles: list[Role] = Field(description="Roles you may choose")
    role_editable: bool
    organization: FormOrganizationOut
    scopes: FormScopesOut
    manager: FormManagerOut
    sections: FormSectionsOut
    guardians: FormGuardiansOut
    initial_password: FormInitialPasswordOut
    email_optional: bool
    required_fields: list[str] = Field(description="Dotted field names, e.g. personal_info.phone")
    defaults: FormDefaultsOut


class UserFormOptionsResponse(SuccessResponse):
    form_options: UserFormOptionsOut
