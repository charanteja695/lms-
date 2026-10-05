from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import CurrentAuth, DbSession, SessionIdParam, SettingsDep
from app.api.responses import AUTHENTICATED, errors
from app.domain.enums import SessionStatus
from app.models.session import ProctorSession
from app.schemas.proctoring import (
    DirectiveOut,
    MonitorSessionResponse,
    NoteIn,
    SessionDetailOut,
    SessionListResponse,
    SessionOut,
    WarnIn,
)
from app.schemas.types import id_field
from app.services.monitor_service import MonitorService

router = APIRouter(prefix="/monitor", tags=["Live monitoring"])


class MonitorQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_id: id_field("test_id", "1755000000000555") | None = None  # type: ignore[valid-type]
    status: SessionStatus | None = Field(default=None, description="Default: active, ready and submitted sessions")
    min_risk: int | None = Field(default=None, ge=0, le=100)
    only_critical: bool = False
    page: int = Field(default=1, ge=1, le=10_000)
    per_page: int = Field(default=50, ge=1, le=200)


async def _detail(service: MonitorService, session: ProctorSession, message: str) -> MonitorSessionResponse:
    return MonitorSessionResponse(
        message=message,
        session=SessionDetailOut.model_validate(session),
        events=await service.recent_events(session),
        directives=[DirectiveOut.model_validate(d) for d in await service.directives(session)],
    )


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="Live sessions, highest risk first",
    description="Exam managers see every session; institution staff their own students' (platform tests); an employer's "
    "members the sessions of its hiring assessments.",
    responses=errors(*AUTHENTICATED),
)
async def list_sessions(query: Annotated[MonitorQuery, Query()], auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> SessionListResponse:
    rows, total, exact = await MonitorService(db, settings).list_sessions(
        auth, test_id=query.test_id, status=query.status, min_risk=query.min_risk, only_critical=query.only_critical, page=query.page, per_page=query.per_page
    )
    return SessionListResponse(
        message="Sessions retrieved successfully.",
        sessions=[SessionOut.model_validate(s) for s in rows],
        page_context=PageContext.build(page=query.page, per_page=query.per_page, total=total, is_exact=exact, sort_column="risk_score", sort_order=SortOrder.DESC),
    )


@router.get("/sessions/{session_id}", response_model=MonitorSessionResponse, summary="One live session: risk breakdown, recent events, directives", responses=errors(*AUTHENTICATED, 404))
async def get_session(session_id: SessionIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> MonitorSessionResponse:
    service = MonitorService(db, settings)
    return await _detail(service, await service.get(session_id, auth), "Session retrieved successfully.")


@router.post(
    "/sessions/{session_id}/warn",
    response_model=MonitorSessionResponse,
    summary="Warn the student",
    description="Shown to the student with their next heartbeat, and scored as a staff action (no risk points).",
    responses=errors(*AUTHENTICATED, 404, 409, 422),
)
async def warn(session_id: SessionIdParam, data: WarnIn, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> MonitorSessionResponse:
    service = MonitorService(db, settings)
    session = await service.get(session_id, auth)
    await service.warn(session, data.message, auth)
    return await _detail(service, session, "Warning sent.")


@router.post(
    "/sessions/{session_id}/pause",
    response_model=MonitorSessionResponse,
    summary="Pause the attempt (stops the student's clock)",
    description="Asks assessment-service to pause the attempt; recorded only once it agrees (502 `ASSESSMENT_UNAVAILABLE` "
    "means nothing changed). The paused time is given back when resumed.",
    responses=errors(*AUTHENTICATED, 404, 409, 502),
)
async def pause(session_id: SessionIdParam, data: NoteIn, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> MonitorSessionResponse:
    service = MonitorService(db, settings)
    session = await service.get(session_id, auth)
    await service.pause(session, data.message, auth)
    return await _detail(service, session, "Attempt paused.")


@router.post("/sessions/{session_id}/resume", response_model=MonitorSessionResponse, summary="Resume a paused attempt", responses=errors(*AUTHENTICATED, 404, 409, 502))
async def resume(session_id: SessionIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> MonitorSessionResponse:
    service = MonitorService(db, settings)
    session = await service.get(session_id, auth)
    await service.resume(session, auth)
    return await _detail(service, session, "Attempt resumed.")


@router.post(
    "/sessions/{session_id}/terminate",
    response_model=MonitorSessionResponse,
    summary="End the attempt now",
    description="The attempt is submitted as it stands and always goes to a person for review: terminating is a "
    "critical event, and only a human decision can invalidate it.",
    responses=errors(*AUTHENTICATED, 404, 409, 502),
)
async def terminate(session_id: SessionIdParam, data: NoteIn, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> MonitorSessionResponse:
    service = MonitorService(db, settings)
    session = await service.get(session_id, auth)
    await service.terminate(session, data.message, auth)
    return await _detail(service, session, "Attempt terminated.")

