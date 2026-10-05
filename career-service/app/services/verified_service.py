"""Verified profile items, built from platform events. Each handler is idempotent (an item is keyed by user, kind and the
source's own id) and tolerant of arriving out of order: a certificate can be issued before this service has heard of the
student or the course.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.ids import new_public_id
from app.core.time import utcnow
from app.domain.enums import ItemKind, ItemSource
from app.models.profile import ProfileItem
from app.models.refs import AttemptResult
from app.services.profile_service import ProfileService

# Practice tests are for learning, hiring tests belong to an employer: neither is a skill score on a student's profile.
SCORED_KINDS = {"topic", "module", "final"}


def _int(value: Any) -> int | None:
    try:
        return int(str(value)) if value not in (None, "") else None
    except ValueError:
        return None


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class VerifiedService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.profiles = ProfileService(db, settings)

    async def _item(self, user_id: int, kind: ItemKind, source_ref: str) -> ProfileItem | None:
        return (await self.db.execute(select(ProfileItem).where(ProfileItem.user_id == user_id, ProfileItem.kind == kind, ProfileItem.source_ref == source_ref))).scalar_one_or_none()

    async def _upsert(self, user_id: int, kind: ItemKind, source: ItemSource, source_ref: str, data: dict[str, Any]) -> tuple[ProfileItem, bool]:
        """Create or refresh a verified item and make it active. Returns ``(item, changed)``."""
        item = await self._item(user_id, kind, source_ref)
        if item is None:
            item = ProfileItem(public_id=new_public_id(), user_id=user_id, kind=kind, verified=True, source=source, source_ref=source_ref, data=data, position=0, active=True)
            self.db.add(item)
            await self.db.flush()
            return item, True
        changed = item.data != data or not item.active
        item.data, item.active, item.inactive_reason, item.inactive_at = data, True, None, None
        return item, changed

    async def _deactivate(self, item: ProfileItem | None, reason: str) -> bool:
        if item is None or not item.active:
            return False
        item.active, item.inactive_reason, item.inactive_at = False, reason, utcnow()
        return True

    # ------------------------------------------------------------------ certificates and completed courses
    async def certificate_issued(self, payload: dict[str, Any]) -> None:
        """``certificate.issued`` {certificate_id, student_user_id, organization_id, course_id, grade, score_percent, completion_date,
        issued_at, verification_url}: a verified certificate, and the verified fact that the course was completed."""
        user_id, certificate_id, course_id = _int(payload.get("student_user_id")), _int(payload.get("certificate_id")), _int(payload.get("course_id"))
        if user_id is None or certificate_id is None or course_id is None:
            return
        profile = await self.profiles.get_or_create(user_id, _int(payload.get("organization_id")))
        _, cert_changed = await self._upsert(
            user_id, ItemKind.CERTIFICATE, ItemSource.CERTIFICATE, str(certificate_id),
            {
                "certificate_id": str(certificate_id), "course_id": str(course_id), "grade": payload.get("grade"), "score_percent": _float(payload.get("score_percent")),
                "issued_at": payload.get("issued_at"), "verification_url": payload.get("verification_url"),
            },
        )
        _, course_changed = await self._upsert(
            user_id, ItemKind.COURSE, ItemSource.CERTIFICATE, str(course_id), {"course_id": str(course_id), "completed_at": payload.get("completion_date") or payload.get("issued_at")}
        )
        if cert_changed or course_changed:
            await self.profiles.touch(profile)

    async def certificate_revoked(self, payload: dict[str, Any]) -> None:
        """A revoked certificate leaves the profile (and every future resume) at once; the course stays only while another
        certificate for it is still valid."""
        user_id, certificate_id = _int(payload.get("student_user_id")), _int(payload.get("certificate_id"))
        if user_id is None or certificate_id is None:
            return
        reason = "certificate revoked"
        cert = await self._item(user_id, ItemKind.CERTIFICATE, str(certificate_id))
        changed = await self._deactivate(cert, reason)
        await self.db.flush()  # the check below reads the database, which must already know this certificate is gone
        course_id = _int(payload.get("course_id")) or (int(cert.data["course_id"]) if cert else None)
        if course_id is not None:
            others = (
                await self.db.execute(select(ProfileItem).where(ProfileItem.user_id == user_id, ProfileItem.kind == ItemKind.CERTIFICATE, ProfileItem.active.is_(True)))
            ).scalars()
            remaining = [c for c in others if str(c.data.get("course_id")) == str(course_id)]
            if not remaining:
                changed = await self._deactivate(await self._item(user_id, ItemKind.COURSE, str(course_id)), reason) or changed
        if changed:
            await self.profiles.touch(await self.profiles.get_or_create(user_id))

    # ------------------------------------------------------------------ assessment scores
    async def attempt_finalized(self, payload: dict[str, Any]) -> None:
        """``attempt.finalized`` {attempt_id, user_id, course_id, test_kind, result, percent, revision, organization_id}. Keeps every
        released attempt; the skill score of a course is the best percent among the *passed* ones (a failed or integrity-invalidated attempt is not a skill to print)."""
        attempt_id, user_id, course_id = _int(payload.get("attempt_id")), _int(payload.get("user_id")), _int(payload.get("course_id"))
        kind = str(payload.get("test_kind") or "")
        if attempt_id is None or user_id is None or course_id is None or kind not in SCORED_KINDS:
            return
        revision = int(payload.get("revision") or 0)
        row = (await self.db.execute(select(AttemptResult).where(AttemptResult.attempt_id == attempt_id))).scalar_one_or_none()
        if row is not None and revision < row.revision:
            return  # an older release arriving late
        if row is None:
            row = AttemptResult(attempt_id=attempt_id, user_id=user_id, course_id=course_id, test_kind=kind, percent=None, result="failed", revision=0)
            self.db.add(row)
        row.percent, row.result, row.revision = _float(payload.get("percent")), str(payload.get("result") or "failed"), revision
        await self.db.flush()
        await self._refresh_score(user_id, course_id, _int(payload.get("organization_id")))

    async def _refresh_score(self, user_id: int, course_id: int, organization_id: int | None) -> None:
        best, attempts = (
            await self.db.execute(
                select(func.max(AttemptResult.percent), func.count()).where(
                    AttemptResult.user_id == user_id, AttemptResult.course_id == course_id, AttemptResult.result == "passed", AttemptResult.percent.is_not(None)
                )
            )
        ).one()
        profile = await self.profiles.get_or_create(user_id, organization_id)
        if best is None:
            changed = await self._deactivate(await self._item(user_id, ItemKind.SKILL_SCORE, str(course_id)), "no valid result")
        else:
            _, changed = await self._upsert(
                user_id, ItemKind.SKILL_SCORE, ItemSource.ASSESSMENT, str(course_id), {"course_id": str(course_id), "best_percent": round(float(best), 1), "attempts": int(attempts)}
            )
        if changed:
            await self.profiles.touch(profile)
