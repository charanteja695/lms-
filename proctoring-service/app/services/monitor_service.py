"""Live monitoring (docs/PRODUCT.md §5.3): staff see running sessions with their live risk and can warn, pause, resume or
terminate an attempt. Pause/resume/terminate act on assessment-service's attempt (which owns the clock) and are recorded
only once it has agreed; a warning is delivered to the student's client with its next heartbeat."""

from typing import Any

from lms_common.pagination import paginate
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.assessment import AssessmentClient, AssessmentRejected, AssessmentUnavailable
from app.core.config import Settings
from app.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.security import AccessTokenClaims
from app.domain.enums import DirectiveKind, EventSource, SessionStatus
from app.models.session import Directive, ProctorEvent, ProctorSession
from app.permissions.policy import can_manage_exams, can_monitor, is_employer_member, is_institution_staff
from app.services.session_service import SessionService


class AssessmentUnavailableError(AppError):
    status_code = 502
    code = "ASSESSMENT_UNAVAILABLE"
    message = "The test service could not carry that out right now. Nothing was changed; try again."


def scope_sessions(stmt: Select[tuple[ProctorSession]], auth: AccessTokenClaims) -> Select[tuple[ProctorSession]]:
    if can_manage_exams(auth):
        return stmt
    if is_employer_member(auth):
        return stmt.where(ProctorSession.test_owner_id == auth.organization_id)
    if is_institution_staff(auth):
        return stmt.where(ProctorSession.organization_id == auth.organization_id, ProctorSession.test_owner_id.is_(None))
    raise PermissionDeniedError()


class MonitorService:
    def __init__(self, db: AsyncSession, settings: Settings, assessment: AssessmentClient | None = None) -> None:
        self.db = db
        self.settings = settings
        self.assessment = assessment or AssessmentClient(settings)
        self.sessions = SessionService(db, settings)

    async def list_sessions(
        self, auth: AccessTokenClaims, *, test_id: int | None, status: str | None, min_risk: int | None, only_critical: bool, page: int, per_page: int
    ) -> tuple[list[ProctorSession], int, bool]:
        stmt = scope_sessions(select(ProctorSession), auth)
        stmt = stmt.where(ProctorSession.status.in_([SessionStatus.ACTIVE, SessionStatus.READY, SessionStatus.SUBMITTED]) if status is None else ProctorSession.status == status)
        if test_id is not None:
            stmt = stmt.where(ProctorSession.test_id == test_id)
        if min_risk is not None:
            stmt = stmt.where(ProctorSession.risk_score >= min_risk)
        if only_critical:
            stmt = stmt.where(ProctorSession.critical.is_(True))
        stmt = stmt.order_by(ProctorSession.risk_score.desc(), ProctorSession.created_at.desc(), ProctorSession.id)
        return await paginate(self.db, stmt, page, per_page)

    async def get(self, public_id: int, auth: AccessTokenClaims, action: str = "view") -> ProctorSession:
        session = await self.sessions.get(public_id)
        if not can_monitor(auth, student_organization_id=session.organization_id, test_owner_id=session.test_owner_id, action=action):
            raise NotFoundError("Session not found.", code="SESSION_NOT_FOUND")
        return session

    async def recent_events(self, session: ProctorSession, limit: int = 100) -> list[dict[str, Any]]:
        rows = (
            await self.db.execute(select(ProctorEvent).where(ProctorEvent.session_id == session.id).order_by(ProctorEvent.occurred_at.desc()).limit(limit))
        ).scalars()
        return [
            {"type": e.event_type, "source": e.source, "points": e.points, "at": e.occurred_at.strftime("%Y-%m-%dT%H:%M:%SZ"), "detail": e.detail}
            for e in rows
        ]

    async def directives(self, session: ProctorSession, limit: int = 50) -> list[Directive]:
        rows = await self.db.execute(select(Directive).where(Directive.session_id == session.id).order_by(Directive.created_at.desc()).limit(limit))
        return list(rows.scalars())

    def _require_running(self, session: ProctorSession) -> int:
        if session.status != SessionStatus.ACTIVE or session.attempt_id is None:
            raise ConflictError("Only a running test can be controlled.", code="SESSION_NOT_ACTIVE")
        return session.attempt_id

    def _record(self, session: ProctorSession, kind: DirectiveKind, message: str | None, actor: AccessTokenClaims) -> None:
        self.db.add(Directive(session_id=session.id, kind=kind, message=message, issued_by=actor.user_id))
        event_type = "warned" if kind == DirectiveKind.WARN else "paused" if kind == DirectiveKind.PAUSE else "terminated" if kind == DirectiveKind.TERMINATE else "resumed"
        if event_type == "resumed":
            self.db.add(ProctorEvent(session_id=session.id, event_type="resumed", source=EventSource.STAFF, actor_user_id=actor.user_id, detail={"message": message}))
        else:
            self.sessions._add_event(session, event_type, EventSource.STAFF, detail={"message": message}, actor=actor.user_id)

    async def _call(self, action: Any) -> None:
        try:
            await action
        except AssessmentRejected as exc:
            raise ConflictError(f"The test service refused: {exc}", code="ATTEMPT_NOT_CONTROLLABLE") from exc
        except AssessmentUnavailable as exc:
            raise AssessmentUnavailableError() from exc

    async def warn(self, session: ProctorSession, message: str, actor: AccessTokenClaims) -> None:
        self._require_running(session)
        self._record(session, DirectiveKind.WARN, message, actor)
        await self.db.commit()

    async def pause(self, session: ProctorSession, reason: str | None, actor: AccessTokenClaims) -> None:
        await self._call(self.assessment.pause(self._require_running(session), reason))
        self._record(session, DirectiveKind.PAUSE, reason, actor)
        await self.db.commit()

    async def resume(self, session: ProctorSession, actor: AccessTokenClaims) -> None:
        if session.attempt_id is None:
            raise ConflictError("This session has no attempt.", code="SESSION_NOT_ACTIVE")
        await self._call(self.assessment.unpause(session.attempt_id))
        self._record(session, DirectiveKind.RESUME, None, actor)
        await self.db.commit()

    async def terminate(self, session: ProctorSession, reason: str | None, actor: AccessTokenClaims) -> None:
        await self._call(self.assessment.terminate(self._require_running(session), reason))
        session.terminated = True
        self._record(session, DirectiveKind.TERMINATE, reason, actor)  # critical: a person will review the attempt
        await self.db.commit()

