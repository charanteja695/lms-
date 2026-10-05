"""The integrity decision (docs/PRODUCT.md §5.3 "After submission").

  attempt.submitted -> wait for snapshot analysis (bounded) -> integrity report
     low risk and nothing critical -> cleared automatically           -> ``integrity.decided`` (clear)
     anything else                 -> a case for a person             -> ``integrity.flagged`` (if not already)
  a person decides reviewed_ok | invalidated (an invalidation needs a written reason)  -> ``integrity.decided``
  the student may appeal an invalidation once; a *different* exam manager decides the appeal.

Nothing in this service ever invalidates an attempt by itself: the only automatic outcome is ``clear``.
"""

import logging
import uuid
from collections import Counter
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import AnalysisStatus, AppealStatus, CaseStatus, Decision, SessionStatus
from app.models.case import IntegrityCase
from app.models.session import ProctorEvent, ProctorSession, Snapshot
from app.permissions.policy import can_decide_appeals, can_monitor
from app.risk import policy
from app.services.outbox import write_event

logger = logging.getLogger(__name__)

_TIMELINE_LIMIT = 300
_PENDING_ANALYSIS = (AnalysisStatus.PENDING, AnalysisStatus.ANALYZING)


def decided_payload(case: IntegrityCase, decision: str) -> dict[str, Any]:
    return {
        "attempt_id": str(case.attempt_id),
        "decision": decision,
        "case_id": str(case.public_id),
        "session_id": str(case.session_public_id),
        "test_id": str(case.test_id),
        "user_id": str(case.user_id),
        "automatic": case.decided_by is None,
        "risk_score": case.risk_score,
    }


class CaseService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    # ------------------------------------------------------------------ the report and the automatic decision

    async def build_report(self, session: ProctorSession) -> dict[str, Any]:
        events = list(
            (await self.db.execute(select(ProctorEvent).where(ProctorEvent.session_id == session.id).order_by(ProctorEvent.occurred_at).limit(5_000))).scalars()
        )
        by_status = Counter(
            status for (status,) in (await self.db.execute(select(Snapshot.analysis_status).where(Snapshot.session_id == session.id))).all()
        )
        flagged = list(
            (await self.db.execute(select(Snapshot).where(Snapshot.session_id == session.id, Snapshot.flagged.is_(True)).order_by(Snapshot.taken_at).limit(50))).scalars()
        )
        total = sum(by_status.values())
        if session.level != "strict":
            ai = "not_applicable"
        elif total == 0 or by_status.get(AnalysisStatus.DONE, 0) == 0:
            ai = "unavailable"  # nothing was analysed: the report must not read as "looked and found nothing"
        elif by_status.get(AnalysisStatus.DONE, 0) < total:
            ai = "partial"
        else:
            ai = "complete"
        return {
            "level": session.level,
            "risk_score": session.risk_score,
            "risk_breakdown": session.risk_breakdown,
            "critical": session.critical,
            "terminated": session.terminated,
            "event_counts": dict(Counter(e.event_type for e in events)),
            "timeline": [
                {"at": e.occurred_at.strftime("%Y-%m-%dT%H:%M:%SZ"), "type": e.event_type, "source": e.source, "points": e.points}
                for e in events[:_TIMELINE_LIMIT]
                if e.event_type != "session_started"
            ],
            "snapshots": {"total": total, **{str(k): v for k, v in by_status.items()}, "flagged": len(flagged)},
            "flagged_snapshots": [str(s.public_id) for s in flagged],
            "ai_analysis": ai,
            "started_at": session.started_at.strftime("%Y-%m-%dT%H:%M:%SZ") if session.started_at else None,
            "ended_at": session.ended_at.strftime("%Y-%m-%dT%H:%M:%SZ") if session.ended_at else None,
        }

    def _reasons(self, session: ProctorSession, report: dict[str, Any]) -> list[str]:
        reasons = []
        if session.terminated:
            reasons.append("The attempt was terminated during the test")
        for name in ("multiple_faces", "different_person", "identity_mismatch"):
            if name in report["event_counts"]:
                reasons.append(f"Analysis reported: {name.replace('_', ' ')}")
        if session.risk_score > self.settings.RISK_CLEAR_MAX:
            reasons.append(f"Risk score {session.risk_score} is above the automatic-clearance limit of {self.settings.RISK_CLEAR_MAX}")
        return reasons

    async def finalize_due(self, limit: int) -> int:
        """Decide sessions whose analysis has finished (or whose wait has run out)."""
        now = utcnow()
        rows = (
            await self.db.execute(
                select(ProctorSession)
                .where(ProctorSession.status == SessionStatus.SUBMITTED, ProctorSession.finalize_due_at <= now)
                .order_by(ProctorSession.finalize_due_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()
        decided = 0
        for session in rows:
            waiting = (
                await self.db.execute(select(func.count()).select_from(Snapshot).where(Snapshot.session_id == session.id, Snapshot.analysis_status.in_(_PENDING_ANALYSIS)))
            ).scalar_one()
            overdue = session.ended_at is not None and now >= session.ended_at + timedelta(seconds=self.settings.ANALYSIS_WAIT_SECONDS)
            if waiting and not overdue:
                session.finalize_due_at = now + timedelta(seconds=max(10, self.settings.WORKER_POLL_SECONDS * 5))
                continue
            await self.finalize(session)
            decided += 1
        await self.db.commit()
        return decided

    async def finalize(self, session: ProctorSession) -> IntegrityCase:
        report = await self.build_report(session)
        reasons = self._reasons(session, report)
        attempt_id = session.attempt_id or 0
        case = IntegrityCase(
            public_id=new_public_id(), session_id=session.id, session_public_id=session.public_id, attempt_id=attempt_id, test_id=session.test_id,
            user_id=session.user_id, organization_id=session.organization_id, test_owner_id=session.test_owner_id,
            severity=policy.severity(session.risk_score, clear_max=self.settings.RISK_CLEAR_MAX, flag_min=self.settings.RISK_FLAG_MIN),
            risk_score=session.risk_score, report=report, reasons=reasons,
        )
        case.id = uuid.uuid4()
        session.status = SessionStatus.CLOSED
        if reasons:
            case.status = CaseStatus.OPEN
            self.db.add(case)
            if not session.flag_emitted:
                session.flag_emitted = True
                write_event(
                    self.db, event_type="integrity.flagged", aggregate_type="integrity_case", aggregate_id=case.id,
                    payload={"attempt_id": str(attempt_id), "session_id": str(session.public_id), "status": "flagged", "risk_score": session.risk_score, "case_id": str(case.public_id)},
                )
        else:  # low risk, nothing critical: the only decision this service takes without a person
            case.status, case.decision, case.decided_at = CaseStatus.FINAL, Decision.CLEAR, utcnow()
            self.db.add(case)
            write_event(self.db, event_type="integrity.decided", aggregate_type="integrity_case", aggregate_id=case.id, payload=decided_payload(case, Decision.CLEAR))
        return case

    # ------------------------------------------------------------------ people

    async def get(self, public_id: int) -> IntegrityCase:
        case = (await self.db.execute(select(IntegrityCase).where(IntegrityCase.public_id == public_id))).scalar_one_or_none()
        if case is None:
            raise NotFoundError("Case not found.", code="CASE_NOT_FOUND")
        return case

    async def get_for_reviewer(self, public_id: int, auth: AccessTokenClaims, *, lock: bool = False) -> IntegrityCase:
        stmt = select(IntegrityCase).where(IntegrityCase.public_id == public_id)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        case = (await self.db.execute(stmt)).scalar_one_or_none()
        if case is None or not can_monitor(auth, student_organization_id=case.organization_id, test_owner_id=case.test_owner_id):
            raise NotFoundError("Case not found.", code="CASE_NOT_FOUND")  # another owner's case is not confirmable by id
        return case

    def overdue(self, case: IntegrityCase) -> bool:
        return case.status in (CaseStatus.OPEN, CaseStatus.UNDER_REVIEW) and case.created_at < utcnow() - timedelta(hours=self.settings.CASE_OVERDUE_HOURS)

    def can_appeal(self, case: IntegrityCase) -> bool:
        return (
            case.status == CaseStatus.DECIDED
            and case.decision == Decision.INVALIDATED
            and case.appeal_status == AppealStatus.NONE
            and case.decided_at is not None
            and utcnow() <= case.decided_at + timedelta(days=self.settings.APPEAL_WINDOW_DAYS)
        )

    async def claim(self, case: IntegrityCase, reviewer: AccessTokenClaims) -> IntegrityCase:
        if case.status not in (CaseStatus.OPEN, CaseStatus.UNDER_REVIEW):
            raise ConflictError("This case has already been decided.", code="CASE_NOT_OPEN")
        if case.assigned_to not in (None, reviewer.user_id):
            raise ConflictError("Another reviewer is already on this case.", code="CASE_ALREADY_CLAIMED")
        if case.status == CaseStatus.OPEN:
            write_event(
                self.db, event_type="integrity.flagged", aggregate_type="integrity_case", aggregate_id=case.id,
                payload={"attempt_id": str(case.attempt_id), "status": "under_review", "case_id": str(case.public_id)},
            )
        case.status, case.assigned_to = CaseStatus.UNDER_REVIEW, reviewer.user_id
        await self.db.commit()
        return case

    async def decide(self, case: IntegrityCase, reviewer: AccessTokenClaims, decision: str, note: str | None) -> IntegrityCase:
        if case.status not in (CaseStatus.OPEN, CaseStatus.UNDER_REVIEW):
            raise ConflictError("This case has already been decided.", code="CASE_NOT_OPEN")
        if case.assigned_to not in (None, reviewer.user_id):
            raise ConflictError("Another reviewer is on this case.", code="CASE_ALREADY_CLAIMED")
        if decision == Decision.INVALIDATED and len((note or "").strip()) < self.settings.MIN_INVALIDATION_NOTE_CHARS:
            raise ValidationFailedError(
                details=[{"field": "note", "code": "REASON_REQUIRED", "message": f"Give a written reason of at least {self.settings.MIN_INVALIDATION_NOTE_CHARS} characters; a person must stand behind an invalidation"}]
            )
        case.status, case.decision, case.decided_by, case.decided_at, case.decision_note = CaseStatus.DECIDED, decision, reviewer.user_id, utcnow(), note
        case.assigned_to = reviewer.user_id
        write_event(self.db, event_type="integrity.decided", aggregate_type="integrity_case", aggregate_id=case.id, payload=decided_payload(case, decision))
        await self.db.commit()
        return case

    async def appeal(self, case: IntegrityCase, student: AccessTokenClaims, reason: str) -> IntegrityCase:
        if case.user_id != student.user_id:
            raise NotFoundError("Case not found.", code="CASE_NOT_FOUND")
        if not self.can_appeal(case):
            raise ConflictError("This decision cannot be appealed (only an invalidation, once, within the appeal window).", code="APPEAL_NOT_ALLOWED")
        case.status, case.appeal_status, case.appeal_reason, case.appealed_at = CaseStatus.APPEALED, AppealStatus.REQUESTED, reason, utcnow()
        await self.db.commit()
        return case

    async def decide_appeal(self, case: IntegrityCase, reviewer: AccessTokenClaims, outcome: str, note: str) -> IntegrityCase:
        if not can_decide_appeals(reviewer):
            raise PermissionDeniedError()
        if case.status != CaseStatus.APPEALED:
            raise ConflictError("This case has no appeal to decide.", code="NO_APPEAL")
        if case.decided_by == reviewer.user_id:
            raise PermissionDeniedError("An appeal is decided by someone other than the first reviewer.", code="SAME_REVIEWER")
        case.appeal_status = AppealStatus.OVERTURNED if outcome == "overturned" else AppealStatus.UPHELD
        case.appeal_decided_by, case.appeal_decided_at, case.appeal_note, case.status = reviewer.user_id, utcnow(), note, CaseStatus.FINAL
        if outcome == "overturned":
            case.decision = Decision.REVIEWED_OK
            write_event(self.db, event_type="integrity.decided", aggregate_type="integrity_case", aggregate_id=case.id, payload={**decided_payload(case, Decision.REVIEWED_OK), "appeal": "overturned"})
        await self.db.commit()
        return case


async def finalize_sweep(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings) -> int:
    async with sessionmaker() as db:
        return await CaseService(db, settings).finalize_due(50)
