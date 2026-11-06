from typing import Any

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, Timestamp, text


class RevokeIn(RequestSchema):
    reason: text(500)  # type: ignore[valid-type]


class CertificateOut(ResponseSchema):
    certificate_id: PublicIdOut = Field(validation_alias="public_id")
    status: str
    student_user_id: PublicIdOut
    organization_id: PublicIdOut | None
    course_id: PublicIdOut
    version_id: PublicIdOut | None
    student_name: str | None
    course_title: str | None
    institution_name: str | None
    completion_date: Timestamp
    score_percent: float
    grade: str | None = Field(validation_alias="grade_label")
    issued_at: Timestamp
    revoked_at: Timestamp | None
    pdf_status: str
    verification_code: str
    verification_url: str = ""
    linkedin_add_url: str = ""


class CertificateResponse(SuccessResponse):
    certificate: CertificateOut


class CertificateListResponse(SuccessResponse):
    certificates: list[CertificateOut]
    page_context: PageContext


class StaffCertificateOut(CertificateOut):
    """Adds what only staff and managers see."""

    attempt_id: PublicIdOut
    revoke_reason: str | None
    pdf_attempts: int
    last_error: str | None


class StaffCertificateResponse(SuccessResponse):
    certificate: StaffCertificateOut


class DownloadOut(ResponseSchema):
    url: str
    filename: str
    expires_in: int


class DownloadResponse(SuccessResponse):
    download: DownloadOut


class EventOut(ResponseSchema):
    event_type: str
    actor_user_id: PublicIdOut | None
    detail: dict[str, Any] | None
    created_at: Timestamp


class EventsResponse(SuccessResponse):
    events: list[EventOut]


class VerificationOut(ResponseSchema):
    """What anyone with the certificate (or its QR code) may learn: no ids of people, no scores' internals."""

    valid: bool
    status: str
    certificate_id: str
    student_name: str | None
    course_title: str | None
    institution_name: str | None
    issuer: str
    completion_date: Timestamp
    grade: str | None
    score_percent: float
    issued_at: Timestamp
    revoked_at: Timestamp | None = None


class VerificationResponse(SuccessResponse):
    verification: VerificationOut
