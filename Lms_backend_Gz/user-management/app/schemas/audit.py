from typing import Any, Literal

from pydantic import Field

from app.schemas.common import ListQuery, PageContext, ResponseSchema, SuccessResponse
from app.schemas.summaries import InstitutionRef, UserRef
from app.schemas.types import OrganizationId, PublicIdOut, Timestamp, UserId, text

AuditCategory = Literal["auth", "user", "institution", "employer", "job"]


class AuditLogListQuery(ListQuery):
    category: AuditCategory | None = Field(default=None, description="auth, user, institution, employer or job")
    action: text(100) | None = Field(default=None, examples=["user.status_changed"])  # type: ignore[valid-type]
    actor_user_id: UserId | None = Field(default=None, description="Changes made by this person")
    user_id: UserId | None = Field(default=None, description="History of this user (as actor or subject)")
    organization_id: OrganizationId | None = Field(default=None, description="Everything in this institution")


class AuditTargetOut(ResponseSchema):
    type: str = Field(examples=["user"])
    id: PublicIdOut | None = Field(description="user_id, organization_id, session_id or job_id")
    name: str | None = Field(examples=["Priya Sharma"])


class AuditLogOut(ResponseSchema):
    audit_log_id: PublicIdOut
    time: Timestamp
    action: str = Field(examples=["user.status_changed"])
    category: str = Field(examples=["user"])
    actor: UserRef | None = Field(description="Null for system actions and unknown sign-in attempts")
    target: AuditTargetOut | None
    institution: InstitutionRef | None
    ip_address: str | None
    user_agent: str | None
    request_id: str | None
    details: dict[str, Any] | None = Field(examples=[{"from": "active", "to": "suspended", "reason": "Fee dues"}])


class AuditLogListResponse(SuccessResponse):
    audit_logs: list[AuditLogOut]
    page_context: PageContext
