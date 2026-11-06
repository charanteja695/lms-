"""The PDF is generated once per certificate (docs/PRODUCT.md §5.4), by the worker, and stored.

A ``pending`` certificate row is the job: the worker claims due rows (``FOR UPDATE SKIP LOCKED``, with a lease, so a
worker that dies mid-render just lets the lease lapse), renders, uploads to S3 and marks it ready. A certificate whose
student's name or course title has not reached this service yet is retried with backoff rather than printed blank.
"""

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.time import utcnow
from app.domain.enums import PdfStatus
from app.models.certificate import Certificate, CertificateEvent
from app.models.refs import CourseRef, InstitutionRef, UserRef
from app.render.pdf import CertificateData, render_pdf
from app.services.issue_service import full_name, verification_url
from app.storage import s3

logger = logging.getLogger(__name__)

_MAX_BACKOFF_SECONDS = 600


def pdf_key(certificate: Certificate) -> str:
    return f"certificates/{certificate.public_id}/certificate.pdf"


class MissingDetails(Exception):
    """The words for the certificate have not arrived from the other services yet."""


class PdfService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def claim(self, limit: int) -> list[int]:
        now = utcnow()
        rows = (
            await self.db.execute(
                select(Certificate)
                .where(Certificate.pdf_status == PdfStatus.PENDING, Certificate.pdf_available_at <= now)
                .order_by(Certificate.pdf_available_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).scalars()
        claimed = []
        for certificate in rows:
            certificate.pdf_attempts += 1
            certificate.pdf_available_at = now + timedelta(seconds=self.settings.PDF_LEASE_SECONDS)
            claimed.append(certificate.public_id)
        await self.db.commit()
        return claimed

    async def _complete_details(self, certificate: Certificate) -> None:
        """Fill words that were missing at issue from the directory (never overwrite what was snapshotted)."""
        if not certificate.student_name:
            certificate.student_name = full_name(await self.db.get(UserRef, certificate.student_user_id))
        if not certificate.course_title:
            course = await self.db.get(CourseRef, certificate.course_id)
            certificate.course_title = course.title if course else None
        if not certificate.institution_name and certificate.organization_id:
            institution = await self.db.get(InstitutionRef, certificate.organization_id)
            certificate.institution_name = institution.name if institution else None
        if not certificate.student_name or not certificate.course_title:
            raise MissingDetails("the student's name or the course title has not arrived yet")

    def data_for(self, certificate: Certificate) -> CertificateData:
        return CertificateData(
            certificate_id=str(certificate.public_id),
            student_name=certificate.student_name or "",
            course_title=certificate.course_title or "",
            institution_name=certificate.institution_name or "",
            completion_date=certificate.completion_date.strftime("%d %B %Y").lstrip("0"),
            score_percent=f"{certificate.score_percent:g}",
            grade=certificate.grade_label or "",
            issuer=self.settings.ISSUER_NAME,
            verification_url=verification_url(self.settings, certificate.verification_code),
            verification_code=certificate.verification_code,
            template=certificate.template_snapshot,
        )

    async def render_one(self, public_id: int) -> None:
        certificate = (await self.db.execute(select(Certificate).where(Certificate.public_id == public_id).with_for_update())).scalar_one_or_none()
        if certificate is None or certificate.pdf_status != PdfStatus.PENDING:
            return
        try:
            await self._complete_details(certificate)
            data = self.data_for(certificate)
            pdf = await asyncio.to_thread(render_pdf, data)  # CPU work stays off the event loop
            key = pdf_key(certificate)
            await s3.put_object(self.settings, key, pdf, content_type="application/pdf")
        except Exception as exc:
            certificate.last_error = f"{exc.__class__.__name__}: {exc}"[:300]
            if certificate.pdf_attempts >= self.settings.PDF_MAX_ATTEMPTS:
                certificate.pdf_status = PdfStatus.FAILED
                self.db.add(CertificateEvent(certificate_id=certificate.id, event_type="pdf_failed", detail={"error": certificate.last_error}))
            else:
                certificate.pdf_available_at = utcnow() + timedelta(seconds=min(5 * 2**certificate.pdf_attempts, _MAX_BACKOFF_SECONDS))
            if not isinstance(exc, MissingDetails):
                logger.exception("PDF generation failed for certificate %s", public_id)
            await self.db.commit()
            return
        certificate.pdf_key, certificate.pdf_status = key, PdfStatus.READY
        certificate.pdf_generated_at, certificate.last_error = utcnow(), None
        self.db.add(CertificateEvent(certificate_id=certificate.id, event_type="pdf_ready", detail={"bytes": len(pdf)}))
        await self.db.commit()


async def generate_due(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings) -> int:
    """One worker sweep: claim due certificates and render each with its own short session."""
    async with sessionmaker() as db:
        claimed = await PdfService(db, settings).claim(settings.PDF_BATCH_SIZE)
    for public_id in claimed:
        async with sessionmaker() as db:
            await PdfService(db, settings).render_one(public_id)
    return len(claimed)
