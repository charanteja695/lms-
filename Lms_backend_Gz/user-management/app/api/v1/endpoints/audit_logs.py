from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentAuth, DbSession
from app.api.responses import errors
from app.schemas.audit import AuditLogListQuery, AuditLogListResponse
from app.schemas.common import PageContext
from app.services.audit_log_service import AuditLogService

router = APIRouter(prefix="/audit-logs", tags=["Audit log"], responses=errors(401, 403))


@router.get(
    "",
    response_model=AuditLogListResponse,
    summary="List audit log entries",
    description="Who did what and when, newest first. Super admins see everything; admins see their institutions "
    "and their own actions; institution heads see their institution. Use `user_id` for one person's history.",
    responses=errors(422),
)
async def list_audit_logs(
    query: Annotated[AuditLogListQuery, Query()], auth: CurrentAuth, db: DbSession
) -> AuditLogListResponse:
    logs, total, is_exact = await AuditLogService(db).list_logs(auth.user, query)
    return AuditLogListResponse(
        message="Audit log retrieved successfully.",
        audit_logs=logs,
        page_context=PageContext.build(
            page=query.page,
            per_page=query.per_page,
            total=total,
            is_exact=is_exact,
            sort_column="time",
            sort_order=query.sort_order,
        ),
    )
