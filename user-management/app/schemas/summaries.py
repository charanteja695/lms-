"""Compact references embedded in other responses. Records always point to each other by public id."""

from typing import Self

from pydantic import Field

from app.core.ids import EXAMPLE_ORGANIZATION_ID
from app.models.institution import Institution
from app.models.user import User
from app.schemas.common import ResponseSchema
from app.schemas.types import PublicIdOut


class UserRef(ResponseSchema):
    user_id: PublicIdOut
    full_name: str = Field(examples=["Priya Sharma"])
    role: str = Field(examples=["staff"])
    email: str | None = Field(examples=["priya.sharma@example.com"])

    @classmethod
    def of(cls, user: User | None) -> Self | None:
        if user is None:
            return None
        return cls(user_id=user.public_id, full_name=user.full_name, role=user.role, email=user.email)


class InstitutionRef(ResponseSchema):
    organization_id: PublicIdOut = Field(json_schema_extra={"examples": [EXAMPLE_ORGANIZATION_ID]})
    name: str = Field(examples=["Springfield High School"])
    code: str = Field(examples=["SPH-HYD"])
    organization_type: str = Field(
        default="institution", examples=["institution"], description="institution or employer"
    )

    @classmethod
    def of(cls, institution: Institution | None) -> Self | None:
        if institution is None:
            return None
        return cls(
            organization_id=institution.public_id,
            name=institution.name,
            code=institution.code,
            organization_type=institution.org_type,
        )
