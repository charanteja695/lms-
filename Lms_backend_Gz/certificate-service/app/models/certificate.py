import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Float, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.domain.enums import CertificateStatus, PdfStatus


class Certificate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An issued certificate. Everything printed on it is snapshotted here (the student's name, the course title, the
    template), so it stays exactly as issued whatever happens to the profiles it was built from. The row is also the
    PDF job: the worker claims ``pending`` rows with a lease, renders once, and stores the file."""

    __tablename__ = "certificates"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)  # the certificate_id
    verification_code: Mapped[str] = mapped_column(String(32), unique=True)  # unguessable; in the QR code and the URL
    student_user_id: Mapped[int] = mapped_column(BigInteger)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    course_id: Mapped[int] = mapped_column(BigInteger)
    version_id: Mapped[int | None] = mapped_column(BigInteger)
    enrollment_id: Mapped[int | None] = mapped_column(BigInteger)
    attempt_id: Mapped[int] = mapped_column(BigInteger)  # the final-test attempt that earned it
    test_id: Mapped[int | None] = mapped_column(BigInteger)
    student_name: Mapped[str | None] = mapped_column(String(200))
    course_title: Mapped[str | None] = mapped_column(String(200))
    institution_name: Mapped[str | None] = mapped_column(String(200))
    completion_date: Mapped[datetime]
    score_percent: Mapped[float] = mapped_column(Float)
    grade_label: Mapped[str | None] = mapped_column(String(60))
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("certificate_templates.id", ondelete="SET NULL"))
    template_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType)

    status: Mapped[str] = mapped_column(String(10), default=CertificateStatus.ISSUED, server_default=CertificateStatus.ISSUED)
    issued_at: Mapped[datetime] = mapped_column(default=utcnow)
    revoked_at: Mapped[datetime | None]
    revoke_reason: Mapped[str | None] = mapped_column(String(500))
    revoked_by: Mapped[int | None] = mapped_column(BigInteger)  # None: revoked by the system (an integrity case)

    pdf_status: Mapped[str] = mapped_column(String(10), default=PdfStatus.PENDING, server_default=PdfStatus.PENDING)
    pdf_key: Mapped[str | None] = mapped_column(String(300))
    pdf_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    pdf_available_at: Mapped[datetime] = mapped_column(default=utcnow)
    pdf_generated_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(String(300))

    __table_args__ = (
        # One live certificate per student and course; a revoked one does not block a later, genuine pass.
        Index(
            "uq_certificates_student_course_issued",
            "student_user_id",
            "course_id",
            unique=True,
            postgresql_where=text("status = 'issued'"),
            sqlite_where=text("status = 'issued'"),
        ),
        Index("ix_certificates_student", "student_user_id", "issued_at"),
        Index("ix_certificates_org_issued", "organization_id", "issued_at"),
        Index("ix_certificates_course", "course_id"),
        Index("ix_certificates_attempt", "attempt_id"),
        Index(
            "ix_certificates_pdf_queue",
            "pdf_available_at",
            postgresql_where=text("pdf_status = 'pending'"),
            sqlite_where=text("pdf_status = 'pending'"),
        ),
    )


class CertificateEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Audit trail: issue, PDF generated/failed/regenerated, revoke."""

    __tablename__ = "certificate_events"

    certificate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("certificates.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(30))
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONType)

    __table_args__ = (Index("ix_certificate_events_certificate", "certificate_id", "created_at"),)
