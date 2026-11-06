"""The audit/eval log — platform AI managers only (a cross-org view of what was sent and to whom)."""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import AdminRateLimit, DbSession, RequireAiManagerDep
from app.api.responses import errors
from app.core.ids import parse_public_id
from app.schemas.log import CallLogListResponse, CallLogOut
from app.services.call_log_service import CallLogService

router = APIRouter(prefix="/logs", tags=["Logs"], dependencies=[RequireAiManagerDep, AdminRateLimit])


@router.get("", response_model=CallLogListResponse, summary="List AI call logs", responses=errors(401, 403, 429))
async def list_logs(
    db: DbSession,
    organization_id: Annotated[str | None, Query()] = None,
    service: Annotated[str | None, Query(max_length=60)] = None,
    prompt_key: Annotated[str | None, Query(max_length=80)] = None,
    status: Annotated[str | None, Query(max_length=20)] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CallLogListResponse:
    org_number = parse_public_id(organization_id) if organization_id else None
    logs, total, is_exact = await CallLogService(db).list_logs(organization_id=org_number, service=service, prompt_key=prompt_key, status=status, page=page, per_page=per_page)
    context = PageContext.build(page=page, per_page=per_page, total=total, is_exact=is_exact, sort_column="created_at", sort_order=SortOrder.DESC)
    return CallLogListResponse(message="", logs=[CallLogOut.model_validate(log) for log in logs], page_context=context)
