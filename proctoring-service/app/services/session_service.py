"""Proctor sessions (docs/PRODUCT.md §5.3): the pre-check, the live event stream, the risk score.

  precheck -> ready --(attempt.started)--> active --(attempt.submitted)--> submitted --(decision)--> closed

A session is created by the student *before* the test (the pre-check needs somewhere to live), passes the pre-check, and is
then linked to the attempt when assessment-service announces ``attempt.started``. If a student somehow starts without a
pre-check (assessment-service's enforcement is off, or the event beat the API), the session is created on the spot and the
missing pre-check is itself scored.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.context import RequestContext
from app.core.exceptions import ConflictError, NotFoundError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import EventSource, SessionStatus, SnapshotKind
from app.models.session import Directive, ProctorEvent, ProctorSession, Snapshot, TestRef
from app.risk import policy
from app.schemas.proctoring import PrecheckIn
from app.services.outbox import write_event

logger = logging.getLogger(__name__)

OPEN_STATUSES = (SessionStatus.PRECHECK, SessionStatus.READY, SessionStatus.ACTIVE)


def ready_key(settings: Settings, user_id: int, test_id: int) -> str:
    return f"{settings.READY_KEY_PREFIX}:{user_id}:{test_id}"


def needs_for(level: str) -> list[str]:
    needs = ["consent", "fullscreen"]
    if level == "strict":
        needs += ["camera", "microphone", "bandwidth", "id_photo", "face_enrolment"]
    return needs


class SessionService:
    def __init__(self, db: AsyncSession, settings: Settings, redis: Redis | None = None) -> None:
        self.db = db
        self.settings = settings
        self.redis = redis

    # ------------------------------------------------------------------ loading

    async def get(self, public_id: int) -> ProctorSession:
        session = (await self.db.execute(select(ProctorSession).where(ProctorSession.public_id == public_id))).scalar_one_or_none()
        if session is None:
            raise NotFoundError("Session not found.", code="SESSION_NOT_FOUND")
        return session

    async def get_owned(self, public_id: int, user_id: int, *, lock: bool = False) -> ProctorSession:
        stmt = select(ProctorSession).where(ProctorSession.public_id == public_id)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        session = (await self.db.execute(stmt)).scalar_one_or_none()
        if session is None or session.user_id != user_id:
            raise NotFoundError("Session not found.", code="SESSION_NOT_FOUND")
        return session

    async def for_attempt(self, attempt_id: int, *, lock: bool = False) -> ProctorSession | None:
        stmt = select(ProctorSession).where(ProctorSession.attempt_id == attempt_id).order_by(ProctorSession.created_at.desc()).limit(1)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------------------ pre-check

    async def create(self, auth: AccessTokenClaims, test_id: int, ctx: RequestContext) -> ProctorSession:
        ref = await self.db.get(TestRef, test_id)
        if ref is None or ref.retired or ref.proctoring_level == "none":
            raise NotFoundError("This test is not proctored.", code="TEST_NOT_PROCTORED")
        existing = (
            await self.db.execute(
                select(ProctorSession)
                .where(ProctorSession.user_id == auth.user_id, ProctorSession.test_id == test_id, ProctorSession.status.in_(OPEN_STATUSES))
                .order_by(ProctorSession.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing  # a second tab or a reload: the same pre-check
        session = ProctorSession(
            public_id=new_public_id(), test_id=test_id, user_id=auth.user_id, organization_id=auth.organization_id,
            test_owner_id=ref.owner_organization_id, level=ref.proctoring_level, risk_breakdown={},
            ip_address=ctx.ip_address, user_agent=ctx.user_agent,
        )
        session.id = uuid.uuid4()
        self.db.add(session)
        await self.db.commit()
        return session

    async def precheck(self, session: ProctorSession, data: PrecheckIn, ctx: RequestContext) -> list[dict[str, str]]:
        """Evaluate the system check. Returns the failures (empty = ready). A failed check can simply be retried."""
        if session.status not in (SessionStatus.PRECHECK, SessionStatus.READY):
            raise ConflictError("This session has already started.", code="SESSION_ALREADY_STARTED")
        failures: list[dict[str, str]] = []

        def fail(code: str, message: str) -> None:
            failures.append({"code": code, "message": message})

        if not data.consent or data.consent_version != self.settings.CONSENT_VERSION:
            fail("CONSENT_REQUIRED", "You must accept the current proctoring consent to take this test.")
        if not data.fullscreen_supported:
            fail("FULLSCREEN_UNSUPPORTED", "This browser cannot run the test in fullscreen; use a supported browser.")
        if session.level == "strict":
            if not data.camera:
                fail("CAMERA_REQUIRED", "A working camera is required.")
            if not data.microphone:
                fail("MICROPHONE_REQUIRED", "A working microphone is required.")
            if data.bandwidth_kbps < self.settings.MIN_BANDWIDTH_KBPS_STRICT:
                fail("BANDWIDTH_TOO_LOW", f"At least {self.settings.MIN_BANDWIDTH_KBPS_STRICT} kbps is needed to upload snapshots.")
            kinds = set(
                (
                    await self.db.execute(
                        select(Snapshot.kind).where(
                            Snapshot.session_id == session.id, Snapshot.deleted_at.is_(None),
                            Snapshot.kind.in_([SnapshotKind.ID_PHOTO, SnapshotKind.FACE_ENROL]),
                        )
                    )
                ).scalars()
            )
            if SnapshotKind.ID_PHOTO not in kinds:
                fail("ID_PHOTO_REQUIRED", "Capture a photo of your ID.")
            if SnapshotKind.FACE_ENROL not in kinds:
                fail("FACE_ENROLMENT_REQUIRED", "Capture a photo of your face for identity matching.")

        session.precheck = {**data.model_dump(mode="json", exclude={"device_fingerprint"}), "checked_at": utcnow().isoformat(), "failures": [f["code"] for f in failures]}
        session.device_fingerprint = data.device_fingerprint or session.device_fingerprint
        session.ip_address, session.user_agent = ctx.ip_address, ctx.user_agent
        if failures:
            session.status = SessionStatus.PRECHECK
        else:
            session.status, session.consent_at, session.consent_version = SessionStatus.READY, utcnow(), data.consent_version
            await self._set_ready_flag(session)
        await self.db.commit()
        return failures

    async def _set_ready_flag(self, session: ProctorSession) -> None:
        """assessment-service reads this key before it starts the student's clock."""
        if self.redis is None:
            return
        try:
            await self.redis.set(ready_key(self.settings, session.user_id, session.test_id), str(session.public_id), ex=self.settings.READY_TTL_SECONDS)
        except RedisError:
            logger.warning("Could not publish the pre-check ready flag for session %s", session.public_id)

    async def _clear_ready_flag(self, session: ProctorSession) -> None:
        if self.redis is None:
            return
        try:
            await self.redis.delete(ready_key(self.settings, session.user_id, session.test_id))
        except RedisError:
            logger.warning("Could not clear the ready flag for session %s", session.public_id)

    # ------------------------------------------------------------------ events and risk

    def _add_event(
        self, session: ProctorSession, event_type: str, source: str, *, occurred_at: datetime | None = None,
        detail: dict[str, Any] | None = None, scale: float = 1.0, actor: int | None = None,
    ) -> int:
        """Record an event and apply its (capped) points to the live risk. Returns the points it added."""
        already = session.risk_breakdown.get(event_type, 0)
        added = policy.points(event_type, already, scale=scale)
        if added:
            session.risk_breakdown = {**session.risk_breakdown, event_type: already + added}
            session.risk_score = policy.score_of(session.risk_breakdown)
        if policy.is_critical(event_type):
            session.critical = True
        self.db.add(
            ProctorEvent(session_id=session.id, event_type=event_type, source=source, occurred_at=occurred_at or utcnow(), points=added, detail=detail, actor_user_id=actor)
        )
        self._maybe_flag(session)
        return added

    def _maybe_flag(self, session: ProctorSession) -> None:
        """Crossing the live threshold (or seeing anything critical) tells the rest of the platform once, and lights the
        monitor. It flags; a person decides."""
        if session.flag_emitted or session.attempt_id is None or session.status != SessionStatus.ACTIVE:
            return
        if session.risk_score >= self.settings.RISK_FLAG_MIN or session.critical:
            session.flag_emitted = True
            write_event(
                self.db, event_type="integrity.flagged", aggregate_type="proctor_session", aggregate_id=session.id,
                payload={"attempt_id": str(session.attempt_id), "session_id": str(session.public_id), "status": "flagged", "risk_score": session.risk_score},
            )

    def _clamp(self, when: datetime | None) -> datetime:
        now = utcnow()
        if when is None or when.tzinfo is None or abs((when - now).total_seconds()) > self.settings.CLIENT_CLOCK_SKEW_SECONDS:
            return now  # a client clock cannot backdate or postdate the timeline by more than the skew allowance
        return when

    async def record_client_events(self, session: ProctorSession, items: list[Any]) -> tuple[int, list[dict[str, str]]]:
        if session.status != SessionStatus.ACTIVE:
            raise ConflictError("Events are only accepted while the test is running.", code="SESSION_NOT_ACTIVE")
        accepted, rejected = 0, []
        for item in items[: self.settings.MAX_EVENTS_PER_REQUEST]:
            if not policy.allowed(item.type, "client", session.level):  # type: ignore[arg-type]
                rejected.append({"type": item.type, "code": "EVENT_NOT_ALLOWED"})
                continue
            self._add_event(session, item.type, EventSource.CLIENT, occurred_at=self._clamp(item.occurred_at), detail=item.detail)
            accepted += 1
        await self.db.commit()
        return accepted, rejected

    def add_finding(self, session: ProctorSession, finding_type: str, confidence: float, detail: dict[str, Any] | None) -> None:
        """An AI finding above the confidence floor scores in proportion to its confidence."""
        if confidence >= self.settings.AI_MIN_CONFIDENCE and policy.allowed(finding_type, "ai", session.level):  # type: ignore[arg-type]
            self._add_event(session, finding_type, EventSource.AI, detail={**(detail or {}), "confidence": round(confidence, 3)}, scale=confidence)
        else:
            self.db.add(ProctorEvent(session_id=session.id, event_type=finding_type, source=EventSource.AI, points=0, detail={**(detail or {}), "confidence": round(confidence, 3), "ignored": True}))

    # ------------------------------------------------------------------ heartbeat

    async def heartbeat(self, session: ProctorSession, ctx: RequestContext, fingerprint: str | None) -> list[Directive]:
        """Proof of life, and the way staff instructions reach the student. Also notices a changed IP or device."""
        if session.status not in (SessionStatus.ACTIVE, SessionStatus.READY):
            raise ConflictError("This session is not running.", code="SESSION_NOT_ACTIVE")
        now = utcnow()
        session.last_heartbeat_at, session.heartbeat_lost = now, False
        if session.status == SessionStatus.ACTIVE:
            if ctx.ip_address and session.ip_address and ctx.ip_address != session.ip_address:
                self._add_event(session, "ip_changed", EventSource.SYSTEM, detail={"from": session.ip_address, "to": ctx.ip_address})
            if fingerprint and session.device_fingerprint and fingerprint != session.device_fingerprint:
                self._add_event(session, "device_changed", EventSource.SYSTEM)
                session.device_fingerprint = fingerprint
        if ctx.ip_address:
            session.ip_address = ctx.ip_address
        pending = list(
            (await self.db.execute(select(Directive).where(Directive.session_id == session.id, Directive.delivered_at.is_(None)).order_by(Directive.created_at))).scalars()
        )
        for directive in pending:
            directive.delivered_at = now
        await self.db.commit()
        return pending

    async def sweep_lost_heartbeats(self, limit: int) -> int:
        """Score a session whose client has gone quiet (once per gap, so a long outage is not scored every sweep)."""
        cutoff = utcnow() - timedelta(seconds=self.settings.HEARTBEAT_LOST_AFTER_SECONDS)
        rows = (
            await self.db.execute(
                select(ProctorSession)
                .where(ProctorSession.status == SessionStatus.ACTIVE, ProctorSession.heartbeat_lost.is_(False), ProctorSession.last_heartbeat_at < cutoff)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()
        for session in rows:
            session.heartbeat_lost = True
            self._add_event(session, "heartbeat_lost", EventSource.SYSTEM, detail={"last_heartbeat_at": session.last_heartbeat_at.isoformat() if session.last_heartbeat_at else None})
        await self.db.commit()
        return len(rows)

    # ------------------------------------------------------------------ from assessment-service's events

    async def on_attempt_started(self, payload: dict[str, Any]) -> None:
        """``attempt.started``: link the pre-checked session to the attempt, and make it the single live session."""
        level = payload.get("proctoring_level")
        if level not in ("basic", "strict"):
            return
        user_id, test_id, attempt_id = int(payload["user_id"]), int(payload["test_id"]), int(payload["attempt_id"])
        if await self.for_attempt(attempt_id) is not None:
            return  # a redelivery
        candidates = list(
            (
                await self.db.execute(
                    select(ProctorSession)
                    .where(ProctorSession.user_id == user_id, ProctorSession.test_id == test_id, ProctorSession.status.in_(OPEN_STATUSES))
                    .order_by(ProctorSession.created_at.desc())
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalars()
        )
        chosen = next((s for s in candidates if s.status == SessionStatus.READY), None) or next(iter(candidates), None)
        precheck_missing = chosen is None or chosen.status != SessionStatus.READY
        ref = await self.db.get(TestRef, test_id)
        if chosen is None:
            chosen = ProctorSession(
                public_id=new_public_id(), test_id=test_id, user_id=user_id,
                organization_id=int(payload["organization_id"]) if payload.get("organization_id") else None,
                test_owner_id=ref.owner_organization_id if ref else None, level=level, risk_breakdown={},
            )
            chosen.id = uuid.uuid4()
            self.db.add(chosen)
            await self.db.flush()
        now = utcnow()
        chosen.attempt_id, chosen.status, chosen.started_at, chosen.last_heartbeat_at = attempt_id, SessionStatus.ACTIVE, now, now
        chosen.level = level
        for other in candidates:  # the single active session: anything else this student had open is superseded
            if other.id != chosen.id:
                if other.status == SessionStatus.ACTIVE:
                    self._add_event(chosen, "multiple_sessions", EventSource.SYSTEM, detail={"other_session": str(other.public_id)})
                other.status = SessionStatus.SUPERSEDED
        if precheck_missing:
            self._add_event(chosen, "precheck_missing", EventSource.SYSTEM)
        self.db.add(ProctorEvent(session_id=chosen.id, event_type="session_started", source=EventSource.SYSTEM, occurred_at=now, detail={"attempt_id": str(attempt_id)}))
        await self._clear_ready_flag(chosen)

    async def on_attempt_submitted(self, payload: dict[str, Any]) -> None:
        """``attempt.submitted``: the sitting is over; the integrity decision is made once analysis has had its chance."""
        if payload.get("proctoring_level") not in ("basic", "strict"):
            return
        attempt_id = int(payload["attempt_id"])
        session = await self.for_attempt(attempt_id, lock=True)
        if session is None:  # attempt.started never reached us: make the session now so the attempt is still reviewed
            await self.on_attempt_started(payload)
            session = await self.for_attempt(attempt_id, lock=True)
        if session is None or session.status != SessionStatus.ACTIVE:
            return
        now = utcnow()
        if payload.get("submit_reason") == "terminated" and not session.terminated:
            session.terminated = True
            self._add_event(session, "terminated", EventSource.STAFF, detail={"by": "assessment-service"})
        # The decision waits for pending snapshot analysis, but only for ANALYSIS_WAIT_SECONDS after the end
        # (see CaseService.finalize_due); it is first considered straight away.
        session.status, session.ended_at, session.finalize_due_at = SessionStatus.SUBMITTED, now, now

    async def abandon_stale(self, *, older_than_hours: int = 24) -> int:
        """A pre-check nobody followed with an attempt is not kept open forever."""
        cutoff = utcnow() - timedelta(hours=older_than_hours)
        result = await self.db.execute(
            update(ProctorSession)
            .where(ProctorSession.status.in_([SessionStatus.PRECHECK, SessionStatus.READY]), ProctorSession.updated_at < cutoff)
            .values(status=SessionStatus.ABANDONED)
        )
        await self.db.commit()
        return int(getattr(result, "rowcount", 0) or 0)
