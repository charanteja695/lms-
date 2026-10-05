"""Pickers for the organisations a job or a drive names, from this service's own copy of them.

user-management only lets a member list their own organisation, so a recruiter could not find an institution to restrict a job to,
and an institution head could not find a company to invite to a drive. These read the ``org_refs`` read-model and the employer
profiles instead: names only, nothing private.
"""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import ResponseSchema, SuccessResponse
from lms_common.pagination import LIKE_ESCAPE, contains_pattern
from pydantic import Field
from sqlalchemy import ColumnElement, func, select

from app.api.deps import CurrentAuth, DbSession, RequireEmployerOrManager
from app.api.responses import AUTHENTICATED, errors
from app.domain.enums import EmployerStatus
from app.models.employer import EmployerProfile
from app.models.refs import OrgRef

router = APIRouter(prefix="/directory", tags=["Directory"])

_LIMIT = 20


class OrgOptionOut(ResponseSchema):
    organization_id: str
    name: str
    industry: str | None = None


class OrgOptionsResponse(SuccessResponse):
    organizations: list[OrgOptionOut] = Field(default_factory=list)


def _named(q: str | None) -> ColumnElement[bool] | None:
    return func.lower(OrgRef.name).like(contains_pattern(q.strip().lower()), escape=LIKE_ESCAPE) if q and q.strip() else None


@router.get("/companies", response_model=OrgOptionsResponse, summary="Verified companies, by name", responses=errors(*AUTHENTICATED))
async def companies(auth: CurrentAuth, db: DbSession, q: Annotated[str | None, Query(max_length=100)] = None) -> OrgOptionsResponse:
    """Any signed-in person: a verified company's name is already public (its job posts carry it)."""
    stmt = (
        select(OrgRef.org_id, OrgRef.name, OrgRef.industry)
        .join(EmployerProfile, EmployerProfile.organization_id == OrgRef.org_id)
        .where(OrgRef.org_type == "employer", OrgRef.active.is_(True), EmployerProfile.status == EmployerStatus.VERIFIED)
    )
    if (named := _named(q)) is not None:
        stmt = stmt.where(named)
    rows = (await db.execute(stmt.order_by(OrgRef.name).limit(_LIMIT))).all()
    return OrgOptionsResponse(message="", organizations=[OrgOptionOut(organization_id=str(i), name=n or "Company", industry=ind) for i, n, ind in rows])


@router.get("/institutions", response_model=OrgOptionsResponse, summary="Active institutions, by name", responses=errors(*AUTHENTICATED))
async def institutions(auth: RequireEmployerOrManager, db: DbSession, q: Annotated[str | None, Query(max_length=100)] = None) -> OrgOptionsResponse:
    """A company's team (to restrict a job to some institutions' students) and careers managers."""
    stmt = select(OrgRef.org_id, OrgRef.name).where(OrgRef.org_type == "institution", OrgRef.active.is_(True))
    if (named := _named(q)) is not None:
        stmt = stmt.where(named)
    rows = (await db.execute(stmt.order_by(OrgRef.name).limit(_LIMIT))).all()
    return OrgOptionsResponse(message="", organizations=[OrgOptionOut(organization_id=str(i), name=n or "Institution") for i, n in rows])
