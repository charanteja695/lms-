"""Shapes for the permission catalog, the role matrix and one person's permissions (super admin screens)."""

from pydantic import Field

from app.schemas.common import RequestSchema, ResponseSchema, SuccessResponse
from app.schemas.types import text


class CatalogEntry(ResponseSchema):
    key: str
    label: str
    description: str
    modules: list[str]
    audience: str = Field(description="platform (admins), institution, employer or member: who may hold it")
    default_roles: list[str]


class CatalogResponse(SuccessResponse):
    permissions: list[CatalogEntry]


class RoleCell(ResponseSchema):
    key: str
    allowed: bool
    changed: bool = Field(description="True when a super admin changed this from the catalog default")


class RoleRow(ResponseSchema):
    role: str
    permissions: list[RoleCell]


class RoleMatrixResponse(SuccessResponse):
    roles: list[RoleRow]


class PermissionChanges(RequestSchema):
    changes: dict[str, bool | None] = Field(
        min_length=1,
        max_length=60,
        description="permission key → true (allow), false (remove), null (back to the default)",
    )
    reason: text(300) | None = None  # type: ignore[valid-type]


class PersonCell(ResponseSchema):
    key: str
    from_role: bool = Field(description="Their role (or, for an admin, their scopes) gives it")
    override: bool | None = Field(description="This person's own grant (true) or removal (false); null when none")
    allowed: bool = Field(description="The result")


class PersonPermissions(ResponseSchema):
    editable: bool = Field(description="False for a super admin, who always holds everything")
    permissions: list[PersonCell]


class PersonPermissionsResponse(SuccessResponse):
    user_permissions: PersonPermissions
