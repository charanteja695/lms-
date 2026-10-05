"""Reading certificates: who sees which, the public verification lookup, PDF download links and regeneration."""

from urllib.parse import quote

from lms_common.pagination import paginate
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import CertificateStatus, PdfStatus
from app.models.certificate import Certificate, CertificateEvent
from app.permissions.policy import can_manage_certificates, can_view_certificate, is_institution_staff, is_student
from app.services.issue_service import verification_url
from app.storage import s3


def linkedin_add_url(certificate: Certificate, settings: Settings) -> str:
    """LinkedIn's "Add to profile" link for a certification (docs/PRODUCT.md §5.4: shareable to LinkedIn)."""
    return (
        "https://www.linkedin.com/profile/add?startTask=CERTIFICATION_NAME"
        f"&name={quote(certificate.course_title or 'Course completion')}"
        f"&organizationName={quote(settings.ISSUER_NAME)}"
        f"&issueYear={certificate.completion_date.year}&issueMonth={certificate.completion_date.month}"
        f"&certUrl={quote(verification_url(settings, certificate.verification_code), safe='')}"
        f"&certId={certificate.public_id}"
    )


def scope_certificates(stmt: Select[tuple[Certificate]], auth: AccessTokenClaims) -> Select[tuple[Certificate]]:
    if is_student(auth):
        return stmt.where(Certificate.student_user_id == auth.user_id)
    if can_manage_certificates(auth):
        return stmt
    if is_institution_staff(auth):
        return stmt.where(Certificate.organization_id == auth.organization_id)
    raise PermissionDeniedError()


class CertificateService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def get(self, public_id: int, auth: AccessTokenClaims | None = None) -> Certificate:
        certificate = (await self.db.execute(select(Certificate).where(Certificate.public_id == public_id))).scalar_one_or_none()
        if certificate is None or (
            auth is not None
            and not can_view_certificate(auth, student_user_id=certificate.student_user_id, organization_id=certificate.organization_id)
        ):
            raise NotFoundError("Certificate not found.", code="CERTIFICATE_NOT_FOUND")
        return certificate

    async def get_by_code(self, code: str) -> Certificate:
        certificate = (await self.db.execute(select(Certificate).where(Certificate.verification_code == code))).scalar_one_or_none()
        if certificate is None:
            raise NotFoundError("No certificate matches this code.", code="CERTIFICATE_NOT_FOUND")
        return certificate

    async def list_certificates(
        self, auth: AccessTokenClaims, *, course_id: int | None, student_user_id: int | None, status: str | None, pdf_status: str | None,
        page: int, per_page: int, ascending: bool,
    ) -> tuple[list[Certificate], int, bool]:
        stmt = scope_certificates(select(Certificate), auth)
        if course_id is not None:
            stmt = stmt.where(Certificate.course_id == course_id)
        if student_user_id is not None and not is_student(auth):
            stmt = stmt.where(Certificate.student_user_id == student_user_id)
        if status:
            stmt = stmt.where(Certificate.status == status)
        if pdf_status:
            stmt = stmt.where(Certificate.pdf_status == pdf_status)
        stmt = stmt.order_by(Certificate.issued_at.asc() if ascending else Certificate.issued_at.desc(), Certificate.id)
        return await paginate(self.db, stmt, page, per_page)

    async def download(self, certificate: Certificate, auth: AccessTokenClaims) -> tuple[str, str]:
        """A short-lived link to the stored PDF. A revoked certificate's PDF is no longer handed to the student."""
        if certificate.status == CertificateStatus.REVOKED and not (can_manage_certificates(auth) or is_institution_staff(auth)):
            raise PermissionDeniedError("This certificate has been revoked.", code="CERTIFICATE_REVOKED")
        if certificate.pdf_status != PdfStatus.READY or not certificate.pdf_key:
            raise ConflictError("The PDF is not ready yet; try again shortly.", code="PDF_NOT_READY")
        url = await s3.presign_get(self.settings, certificate.pdf_key, expires_seconds=self.settings.S3_DOWNLOAD_URL_EXPIRES_SECONDS)
        return url, f"certificate-{certificate.public_id}.pdf"

    async def regenerate(self, certificate: Certificate, actor_user_id: int) -> Certificate:
        """Render again (a failed PDF, or details that arrived late). The same content gives the same file."""
        certificate.pdf_status, certificate.pdf_attempts, certificate.pdf_available_at = PdfStatus.PENDING, 0, utcnow()
        certificate.last_error = None
        self.db.add(CertificateEvent(certificate_id=certificate.id, event_type="pdf_regenerate_requested", actor_user_id=actor_user_id))
        await self.db.commit()
        return certificate

    async def events(self, certificate: Certificate) -> list[CertificateEvent]:
        rows = await self.db.execute(
            select(CertificateEvent).where(CertificateEvent.certificate_id == certificate.id).order_by(CertificateEvent.created_at)
        )
        return list(rows.scalars())
