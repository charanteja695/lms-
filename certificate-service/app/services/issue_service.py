"""Issuing and revoking certificates from assessment-service's events (docs/PRODUCT.md §5.4).

  course.passed        a final test passed and released  -> issue (idempotent by attempt; one live certificate per
                                                            student and course)
  course.pass_revoked  an integrity case invalidated it    -> revoke that certificate

Everything printed is snapshotted at issue. The student's name may not have reached this service yet (the user event can
lag); the row is issued anyway and the PDF worker fills the missing words from the directory when it renders.
"""

import logging
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError
from app.core.ids import new_public_id
from app.core.time import utcnow
from app.domain.enums import CertificateStatus
from app.models.certificate import Certificate, CertificateEvent
from app.models.refs import CourseRef, InstitutionRef, UserRef
from app.render.layout import grade_for
from app.services.outbox import write_event
from app.services.template_service import TemplateService

logger = logging.getLogger(__name__)


def verification_url(settings: Settings, code: str) -> str:
    return f"{settings.PUBLIC_VERIFY_BASE_URL.rstrip('/')}/{code}"


def _iso(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


def full_name(user: UserRef | None) -> str | None:
    return f"{user.first_name} {user.last_name}".strip() if user else None


def issued_payload(certificate: Certificate, settings: Settings) -> dict[str, Any]:
    return {
        "certificate_id": str(certificate.public_id),
        "student_user_id": str(certificate.student_user_id),
        "organization_id": str(certificate.organization_id) if certificate.organization_id else None,
        "course_id": str(certificate.course_id),
        "version_id": str(certificate.version_id) if certificate.version_id else None,
        "attempt_id": str(certificate.attempt_id),
        "score_percent": certificate.score_percent,
        "grade": certificate.grade_label,
        "completion_date": _iso(certificate.completion_date),
        "issued_at": _iso(certificate.issued_at),
        "verification_url": verification_url(settings, certificate.verification_code),
    }


class IssueService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def issue_from_pass(self, payload: dict[str, Any]) -> Certificate | None:
        student_id, course_id, attempt_id = int(payload["student_user_id"]), int(payload["course_id"]), int(payload["attempt_id"])
        same_attempt = (await self.db.execute(select(Certificate).where(Certificate.attempt_id == attempt_id))).scalar_one_or_none()
        if same_attempt is not None:
            return same_attempt  # a redelivered event
        live = (
            await self.db.execute(
                select(Certificate).where(
                    Certificate.student_user_id == student_id, Certificate.course_id == course_id, Certificate.status == CertificateStatus.ISSUED
                )
            )
        ).scalar_one_or_none()
        if live is not None:
            logger.info("A pass for a course that already has a live certificate; keeping the existing one")
            return live

        user = await self.db.get(UserRef, student_id)
        course = await self.db.get(CourseRef, course_id)
        organization_id = int(payload["organization_id"]) if payload.get("organization_id") else None
        institution = await self.db.get(InstitutionRef, organization_id) if organization_id else None
        template_id, snapshot = await TemplateService(self.db).resolve(course_id)
        percent = float(payload.get("percent") or 0.0)
        passed_at = payload.get("passed_at")
        completion = datetime.strptime(passed_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC) if passed_at else utcnow()

        certificate = Certificate(
            public_id=new_public_id(),
            verification_code=secrets.token_urlsafe(12),
            student_user_id=student_id,
            organization_id=organization_id,
            course_id=course_id,
            version_id=int(payload["version_id"]) if payload.get("version_id") else None,
            enrollment_id=int(payload["enrollment_id"]) if payload.get("enrollment_id") else None,
            attempt_id=attempt_id,
            test_id=int(payload["test_id"]) if payload.get("test_id") else None,
            student_name=full_name(user),
            course_title=course.title if course else None,
            institution_name=institution.name if institution else None,
            completion_date=completion,
            score_percent=percent,
            grade_label=grade_for(percent, snapshot["grade_bands"]),
            template_id=template_id,
            template_snapshot=snapshot,
        )
        certificate.id = uuid.uuid4()
        try:
            async with self.db.begin_nested():
                self.db.add(certificate)
                await self.db.flush()
        except IntegrityError:  # another worker issued it first
            return None
        self.db.add(CertificateEvent(certificate_id=certificate.id, event_type="issued", detail={"attempt_id": str(attempt_id)}))
        write_event(
            self.db, event_type="certificate.issued", aggregate_type="certificate", aggregate_id=certificate.id,
            payload=issued_payload(certificate, self.settings),
        )
        return certificate

    async def revoke(self, certificate: Certificate, *, reason: str, actor_user_id: int | None) -> Certificate:
        """Idempotent: revoking a revoked certificate changes nothing."""
        if certificate.status == CertificateStatus.REVOKED:
            return certificate
        certificate.status = CertificateStatus.REVOKED
        certificate.revoked_at, certificate.revoke_reason, certificate.revoked_by = utcnow(), reason, actor_user_id
        self.db.add(CertificateEvent(certificate_id=certificate.id, event_type="revoked", actor_user_id=actor_user_id, detail={"reason": reason}))
        write_event(
            self.db,
            event_type="certificate.revoked",
            aggregate_type="certificate",
            aggregate_id=certificate.id,
            payload={
                "certificate_id": str(certificate.public_id),
                "student_user_id": str(certificate.student_user_id),
                "organization_id": str(certificate.organization_id) if certificate.organization_id else None,
                "course_id": str(certificate.course_id),
                "reason": reason,
                "revoked_at": _iso(certificate.revoked_at),
            },
        )
        return certificate

    async def revoke_from_event(self, payload: dict[str, Any]) -> None:
        """``course.pass_revoked``: the certificate earned by that attempt (or the student's live one for the course)."""
        certificate = (
            await self.db.execute(select(Certificate).where(Certificate.attempt_id == int(payload["attempt_id"])))
        ).scalar_one_or_none()
        if certificate is None:
            certificate = (
                await self.db.execute(
                    select(Certificate).where(
                        Certificate.student_user_id == int(payload["student_user_id"]),
                        Certificate.course_id == int(payload["course_id"]),
                        Certificate.status == CertificateStatus.ISSUED,
                    )
                )
            ).scalar_one_or_none()
        if certificate is None:
            logger.warning("course.pass_revoked for a pass that has no certificate")
            return
        await self.revoke(certificate, reason=f"Integrity case: {payload.get('reason', 'integrity')}", actor_user_id=None)

    async def revoke_by_manager(self, certificate: Certificate, reason: str, actor_user_id: int) -> Certificate:
        if certificate.status == CertificateStatus.REVOKED:
            raise ConflictError("This certificate is already revoked.", code="ALREADY_REVOKED")
        await self.revoke(certificate, reason=reason, actor_user_id=actor_user_id)
        await self.db.commit()
        return certificate
