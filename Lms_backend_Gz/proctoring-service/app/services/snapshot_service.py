"""Snapshots: metadata of images and audio the browser uploads straight to object storage (docs/PRODUCT.md §5.3).

  upload-url -> browser PUTs to S3 -> register (confirmed to exist) -> analysis queue -> findings -> risk events

The analysis queue is the snapshot rows themselves (claimed with ``FOR UPDATE SKIP LOCKED`` and a lease). Under load only
some periodic snapshots are analysed (the rest are kept and marked as sampled out); with no analyzer configured they are
stored and marked skipped, and the integrity report says analysis was unavailable — it never pretends to have looked.
Media is deleted from storage after ``MEDIA_RETENTION_DAYS`` and every view of it is logged.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.analyzer import AnalyzerClient, AnalyzerRejected, AnalyzerUnavailable
from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.time import utcnow
from app.domain.enums import LIVENESS_POSES, AnalysisStatus, SessionStatus, SnapshotKind
from app.models.session import MediaAccess, ProctorSession, Snapshot
from app.services.session_service import SessionService
from app.storage import s3

logger = logging.getLogger(__name__)

_PRE_TEST_KINDS = (SnapshotKind.ID_PHOTO, SnapshotKind.FACE_ENROL, SnapshotKind.LIVENESS)
_EXTENSIONS = {
    "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "audio/webm": "webm", "audio/ogg": "ogg", "audio/mpeg": "mp3",
    "video/webm": "webm", "video/mp4": "mp4",
}
# Kept for a person to review; the image analyzer does not take them (its contract is single frames and audio clips).
_REVIEW_ONLY = {SnapshotKind.LIVENESS: "face movement check, kept for review", SnapshotKind.VIDEO: "test recording, kept for review"}
_MAX_BACKOFF_SECONDS = 300


class SnapshotService:
    def __init__(self, db: AsyncSession, settings: Settings, analyzer: AnalyzerClient | None = None) -> None:
        self.db = db
        self.settings = settings
        self.analyzer = analyzer or AnalyzerClient(settings)

    # ------------------------------------------------------------------ upload and register

    def _check_kind(self, session: ProctorSession, kind: SnapshotKind) -> None:
        if session.level != "strict":
            raise ConflictError("Snapshots are only taken in strict proctoring.", code="NOT_APPLICABLE")
        if kind in _PRE_TEST_KINDS and session.status not in (SessionStatus.PRECHECK, SessionStatus.READY, SessionStatus.ACTIVE):
            raise ConflictError("This session no longer takes identity photos.", code="SESSION_NOT_OPEN")
        if kind == SnapshotKind.VIDEO:
            if not self.settings.VIDEO_RECORDING_ENABLED:
                raise ConflictError("This test is not recorded.", code="NOT_APPLICABLE")
            # the last chunk is flushed as the student submits, so a just-submitted session still takes it
            if session.status not in (SessionStatus.ACTIVE, SessionStatus.SUBMITTED):
                raise ConflictError("Recording is only accepted while the test is running.", code="SESSION_NOT_ACTIVE")
        elif kind not in _PRE_TEST_KINDS and session.status != SessionStatus.ACTIVE:
            raise ConflictError("Snapshots are only accepted while the test is running.", code="SESSION_NOT_ACTIVE")

    async def upload_url(self, session: ProctorSession, kind: SnapshotKind, content_type: str, *, pose: str | None = None) -> dict[str, Any]:
        self._check_kind(session, kind)
        wanted = "audio/" if kind == SnapshotKind.AUDIO else "video/" if kind == SnapshotKind.VIDEO else "image/"
        if not content_type.startswith(wanted):
            raise ValidationFailedError(details=[{"field": "content_type", "code": "INVALID_TYPE", "message": f"A {kind} upload must be {wanted[:-1]}"}])
        if (kind == SnapshotKind.LIVENESS) != (pose is not None):
            raise ValidationFailedError(details=[{"field": "pose", "code": "POSE_REQUIRED" if pose is None else "NOT_ALLOWED", "message": "A pose goes with liveness frames only"}])
        name = f"{pose}-{uuid.uuid4().hex}" if pose else uuid.uuid4().hex
        key = f"sessions/{session.public_id}/{kind}/{name}.{_EXTENSIONS[content_type]}"
        max_bytes = (self.settings.MAX_VIDEO_CHUNK_MB if kind == SnapshotKind.VIDEO else self.settings.MAX_SNAPSHOT_MB) * 1024 * 1024
        upload = await s3.presign_upload(self.settings, key, content_type=content_type, max_bytes=max_bytes, expires_seconds=self.settings.S3_UPLOAD_URL_EXPIRES_SECONDS)
        return {"key": key, "upload": upload, "expires_in": self.settings.S3_UPLOAD_URL_EXPIRES_SECONDS}

    async def _backlog_high(self) -> bool:
        limit = self.settings.ANALYSIS_BACKLOG_SAMPLING_THRESHOLD
        waiting = (
            await self.db.execute(select(func.count()).select_from(select(Snapshot.id).where(Snapshot.analysis_status == AnalysisStatus.PENDING).limit(limit + 1).subquery()))
        ).scalar_one()
        return int(waiting) > limit

    async def register(self, session: ProctorSession, kind: SnapshotKind, key: str, taken_at: datetime | None) -> Snapshot:
        self._check_kind(session, kind)
        if not key.startswith(f"sessions/{session.public_id}/{kind}/") or ".." in key:
            raise ValidationFailedError(details=[{"field": "key", "code": "INVALID_KEY", "message": "Register only a file uploaded for this session"}])
        try:
            head = await s3.head_object(self.settings, key)
        except s3.ObjectNotFound:
            raise ValidationFailedError(details=[{"field": "key", "code": "FILE_NOT_UPLOADED", "message": "That file has not been uploaded"}]) from None
        now = utcnow()
        sequence = 0
        if kind == SnapshotKind.PERIODIC:
            session.snapshot_seq += 1
            sequence = session.snapshot_seq
        elif kind == SnapshotKind.VIDEO:  # recording chunks play back in this order
            sequence = 1 + int((await self.db.execute(select(func.count()).where(Snapshot.session_id == session.id, Snapshot.kind == SnapshotKind.VIDEO))).scalar_one())
        elif kind == SnapshotKind.LIVENESS:  # the pose, from the file name the upload URL gave it
            sequence = 1 + LIVENESS_POSES.index(key.rsplit("/", 1)[-1].split("-", 1)[0]) if key.rsplit("/", 1)[-1].split("-", 1)[0] in LIVENESS_POSES else 0
        snapshot = Snapshot(
            public_id=new_public_id(), session_id=session.id, kind=kind, sequence=sequence, s3_key=key,
            taken_at=self._when(taken_at, now), size_bytes=int(head.get("ContentLength", 0)), delete_after=now + timedelta(days=self.settings.MEDIA_RETENTION_DAYS),
        )
        if kind in _REVIEW_ONLY:
            snapshot.analysis_status, snapshot.skip_reason = AnalysisStatus.SKIPPED, _REVIEW_ONLY[kind]
        elif not self.analyzer.configured:
            snapshot.analysis_status, snapshot.skip_reason = AnalysisStatus.SKIPPED, "no analyzer configured"
        elif kind == SnapshotKind.PERIODIC and sequence % self.settings.ANALYSIS_SAMPLE_EVERY != 0 and await self._backlog_high():
            snapshot.analysis_status, snapshot.skip_reason = AnalysisStatus.SKIPPED, "sampled out under load"
        self.db.add(snapshot)
        await self.db.commit()
        return snapshot

    def _when(self, taken_at: datetime | None, now: datetime) -> datetime:
        if taken_at is None or taken_at.tzinfo is None or abs((taken_at - now).total_seconds()) > self.settings.CLIENT_CLOCK_SKEW_SECONDS:
            return now
        return taken_at

    # ------------------------------------------------------------------ analysis

    async def claim(self, limit: int) -> list[int]:
        now = utcnow()
        rows = (
            await self.db.execute(
                select(Snapshot)
                .where(Snapshot.analysis_status == AnalysisStatus.PENDING, Snapshot.analysis_available_at <= now, Snapshot.deleted_at.is_(None))
                .order_by(Snapshot.analysis_available_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).scalars()
        claimed = []
        for snapshot in rows:
            snapshot.analysis_attempts += 1
            snapshot.analysis_available_at = now + timedelta(seconds=self.settings.ANALYSIS_LEASE_SECONDS)  # a lease: a crash retries
            claimed.append(snapshot.public_id)
        await self.db.commit()
        return claimed

    async def _reference_url(self, snapshot: Snapshot, session: ProctorSession) -> str | None:
        """The student's own reference photo: their face for a periodic snapshot, their ID for the face they enrolled."""
        wanted = SnapshotKind.ID_PHOTO if snapshot.kind == SnapshotKind.FACE_ENROL else SnapshotKind.FACE_ENROL
        if snapshot.kind in (SnapshotKind.ID_PHOTO, SnapshotKind.AUDIO):
            return None
        reference = (
            await self.db.execute(
                select(Snapshot).where(Snapshot.session_id == session.id, Snapshot.kind == wanted, Snapshot.deleted_at.is_(None)).order_by(Snapshot.created_at.desc()).limit(1)
            )
        ).scalar_one_or_none()
        if reference is None or not reference.s3_key:
            return None
        return await s3.presign_get(self.settings, reference.s3_key, expires_seconds=self.settings.S3_DOWNLOAD_URL_EXPIRES_SECONDS)

    async def analyze_one(self, public_id: int) -> None:
        """Read what the analyzer needs, release the connection, call it, then record the outcome in a fresh transaction:
        no connection is held across the HTTP call."""
        snapshot = (await self.db.execute(select(Snapshot).where(Snapshot.public_id == public_id))).scalar_one_or_none()
        if snapshot is None or snapshot.analysis_status != AnalysisStatus.PENDING or not snapshot.s3_key:
            return
        session = (await self.db.execute(select(ProctorSession).where(ProctorSession.id == snapshot.session_id))).scalar_one()
        job = (snapshot.s3_key, snapshot.kind, session.public_id, session.level)
        attempts = snapshot.analysis_attempts
        try:
            media_url = await s3.presign_get(self.settings, job[0], expires_seconds=self.settings.S3_DOWNLOAD_URL_EXPIRES_SECONDS)
            reference_url = await self._reference_url(snapshot, session)
            await self.db.rollback()  # ends the read transaction: the connection goes back to the pool
            findings = await self.analyzer.analyze(
                snapshot_id=public_id, session_id=job[2], kind=job[1], level=job[3], media_url=media_url, reference_url=reference_url
            )
        except AnalyzerRejected as exc:
            await self._settle(public_id, status=AnalysisStatus.FAILED, reason=str(exc)[:80])
            return
        except Exception as exc:  # unavailable, or anything unexpected: retry with backoff, then give up
            if not isinstance(exc, AnalyzerUnavailable):
                logger.exception("Snapshot analysis failed for %s", public_id)
            if attempts >= self.settings.ANALYSIS_MAX_ATTEMPTS:
                await self._settle(public_id, status=AnalysisStatus.FAILED, reason=f"gave up: {exc}"[:80])
            else:
                await self._settle(public_id, retry_in=min(5 * 2**attempts, _MAX_BACKOFF_SECONDS))
            return
        await self.apply_pushed_findings(public_id, [(f.type, f.confidence, f.detail) for f in findings])

    async def _settle(self, public_id: int, *, status: AnalysisStatus | None = None, reason: str | None = None, retry_in: int | None = None) -> None:
        snapshot = (await self.db.execute(select(Snapshot).where(Snapshot.public_id == public_id).with_for_update())).scalar_one()
        if snapshot.analysis_status != AnalysisStatus.PENDING:
            await self.db.commit()
            return
        if status is not None:
            snapshot.analysis_status, snapshot.skip_reason = status, reason
        if retry_in is not None:
            snapshot.analysis_available_at = utcnow() + timedelta(seconds=retry_in)
        await self.db.commit()

    def _apply(self, snapshot: Snapshot, session: ProctorSession, findings: list[tuple[str, float, dict[str, Any] | None]]) -> None:
        sessions = SessionService(self.db, self.settings)
        for finding_type, confidence, detail in findings:
            sessions.add_finding(session, finding_type, confidence, {**(detail or {}), "snapshot_id": str(snapshot.public_id)})
        snapshot.findings = [{"type": t, "confidence": round(c, 3), "detail": d} for t, c, d in findings]
        snapshot.flagged = any(c >= self.settings.AI_MIN_CONFIDENCE for _, c, _ in findings)
        snapshot.analysis_status = AnalysisStatus.DONE

    async def apply_pushed_findings(self, public_id: int, findings: list[tuple[str, float, dict[str, Any] | None]]) -> Snapshot:
        """An AI worker that analyses asynchronously reports its findings here instead of being called."""
        snapshot = (await self.db.execute(select(Snapshot).where(Snapshot.public_id == public_id).with_for_update())).scalar_one_or_none()
        if snapshot is None:
            raise NotFoundError("Snapshot not found.", code="SNAPSHOT_NOT_FOUND")
        if snapshot.analysis_status == AnalysisStatus.DONE:
            return snapshot  # idempotent: a retried push is not scored twice
        session = (await self.db.execute(select(ProctorSession).where(ProctorSession.id == snapshot.session_id).with_for_update())).scalar_one()
        self._apply(snapshot, session, findings)
        await self.db.commit()
        return snapshot

    # ------------------------------------------------------------------ audited access and retention

    async def view_url(self, snapshot: Snapshot, viewer_user_id: int, reason: str) -> str:
        if snapshot.deleted_at is not None or not snapshot.s3_key:
            raise NotFoundError("This media was deleted after its retention period.", code="MEDIA_DELETED")
        self.db.add(MediaAccess(snapshot_id=snapshot.id, session_id=snapshot.session_id, viewer_user_id=viewer_user_id, reason=reason))
        await self.db.commit()  # the access is logged before the link exists
        return await s3.presign_get(self.settings, snapshot.s3_key, expires_seconds=self.settings.S3_DOWNLOAD_URL_EXPIRES_SECONDS)

    async def purge_expired(self, limit: int = 500) -> int:
        """Delete media past its retention from storage (DPDP: fixed retention, then gone). The metadata stays."""
        now = utcnow()
        rows = (
            await self.db.execute(select(Snapshot).where(Snapshot.delete_after <= now, Snapshot.deleted_at.is_(None)).limit(limit).with_for_update(skip_locked=True))
        ).scalars().all()
        for snapshot in rows:
            if snapshot.s3_key:
                await s3.delete_object(self.settings, snapshot.s3_key)
            snapshot.s3_key, snapshot.deleted_at = None, now
        await self.db.commit()
        return len(rows)


async def analyze_due(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, analyzer: AnalyzerClient | None = None) -> int:
    """One worker sweep: claim due snapshots and analyse each in its own short session (no connection held across HTTP)."""
    async with sessionmaker() as db:
        claimed = await SnapshotService(db, settings, analyzer).claim(settings.ANALYSIS_BATCH)
    for public_id in claimed:
        async with sessionmaker() as db:
            await SnapshotService(db, settings, analyzer).analyze_one(public_id)
    return len(claimed)
