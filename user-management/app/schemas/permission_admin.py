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


class ActionOut(ResponseSchema):
    key: str = Field(description="view, create, update, delete, revoke, export or approve")
    label: str


class PageAction(ResponseSchema):
    action: str
    key: str = Field(description="The cell's permission key, <page>.<action>")
    meaning: str = Field(description="What the action lets them do on this page")
    default_roles: list[str]


class CatalogPage(ResponseSchema):
    key: str
    label: str
    group: str
    description: str
    holders: list[str] = Field(description="Roles that may be given anything on this page")
    actions: list[PageAction] = Field(description="The actions this page has, in column order")


class CatalogResponse(SuccessResponse):
    permissions: list[CatalogEntry] = Field(description="Feature keys: admin scopes and the older company roles' rows")
    actions: list[ActionOut] = Field(description="The matrix columns, in order")
    pages: list[CatalogPage] = Field(description="The matrix rows (module → page), in menu order")
    matrix_roles: list[str] = Field(description="Roles set on the matrix (the others use feature keys)")


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
        max_length=400,
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
