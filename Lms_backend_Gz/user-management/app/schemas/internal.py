"""The internal API other services call with the shared service token."""

from pydantic import Field

from app.schemas.common import RequestSchema, SuccessResponse


class PermissionHoldersRequest(RequestSchema):
    permission: str = Field(min_length=1, max_length=80, examples=["support.agent"])
    user_ids: list[str] = Field(min_length=1, max_length=500, description="Public user ids (strings)")


class PermissionHoldersResponse(SuccessResponse):
    user_ids: list[str] = Field(
        description="Those of the given people who are active and hold the permission right now"
    )
