"""A names-only organisation directory for platform staff (GET /directory/organizations)."""

from pydantic import Field

from app.permissions.roles import OrganizationType
from app.schemas.common import ListQuery, PageContext, ResponseSchema, SuccessResponse
from app.schemas.types import PublicIdOut


class DirectoryQuery(ListQuery):
    type: OrganizationType = Field(description="institution or employer")


class DirectoryEntry(ResponseSchema):
    organization_id: PublicIdOut
    organization_type: OrganizationType
    name: str
    code: str
    city: str
    status: str


class DirectoryResponse(SuccessResponse):
    organizations: list[DirectoryEntry]
    page_context: PageContext


class DirectoryEntryResponse(SuccessResponse):
    organization: DirectoryEntry
