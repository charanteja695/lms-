from sqlalchemy import select
import csv
import io
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from lms_common.envelopes import PageContext, SortOrder
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import (
    CertificateIdParam,
    CurrentAuth,
    DbSession,
    DownloadRateLimit,
    PublicVerifyRateLimit,
    RequireCertificateManager,
    SettingsDep,
)
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import ConflictError, PermissionDeniedError
from app.domain.enums import CertificateStatus, PdfStatus
from app.models.certificate import Certificate
from app.permissions.policy import can_manage_certificates, is_institution_staff, is_student
from app.schemas.certificate import (
    CertificateListResponse,
    CertificateOut,
    CertificateResponse,
    DownloadOut,
    DownloadResponse,
    EventOut,
    EventsResponse,
    RevokeIn,
    StaffCertificateOut,
    StaffCertificateResponse,
    VerificationOut,
    VerificationResponse,
)
from app.schemas.types import id_field
from app.services.certificate_service import CertificateService, linkedin_add_url
from app.services.issue_service import IssueService, verification_url

router = APIRouter(tags=["Certificates"])


class CertificateQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: id_field("course_id", "1755000000001001") | None = None  # type: ignore[valid-type]
    user_id: id_field("user_id", "1755000000004001") | None = None  # type: ignore[valid-type]
    status: CertificateStatus | None = None
    pdf_status: PdfStatus | None = None
    sort_order: SortOrder = SortOrder.DESC
    page: int = Field(default=1, ge=1, le=10_000)
    per_page: int = Field(default=20, ge=1, le=100)


def _out(certificate: Certificate, settings: SettingsDep) -> CertificateOut:
    out = CertificateOut.model_validate(certificate)
    out.verification_url = verification_url(settings, certificate.verification_code)
    out.linkedin_add_url = linkedin_add_url(certificate, settings)
    return out


def _staff_out(certificate: Certificate, settings: SettingsDep) -> StaffCertificateOut:
    out = StaffCertificateOut.model_validate(certificate)
    out.verification_url = verification_url(settings, certificate.verification_code)
    out.linkedin_add_url = linkedin_add_url(certificate, settings)
    return out




class IssueFromPassIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    student_user_id: int
    course_id: int
    attempt_id: int
    version_id: int | None = None
    enrollment_id: int | None = None
    organization_id: int | None = None
    test_id: int | None = None
    percent: float | None = None
    score_percent: float | None = None
    passed_at: str | None = None


@router.post(
    "/certificates/issue-from-pass",
    response_model=CertificateResponse,
    summary="Issue certificate from test pass event",
    responses=errors(*AUTHENTICATED),
)
async def issue_from_pass(
    data: IssueFromPassIn,
    db: DbSession,
    settings: SettingsDep,
) -> CertificateResponse:
    payload = data.model_dump()
    if payload.get("score_percent") is not None and payload.get("percent") is None:
        payload["percent"] = payload["score_percent"]
    cert = await IssueService(db, settings).issue_from_pass(payload)
    if cert is None:
        existing = (
            await db.execute(
                select(Certificate).where(
                    Certificate.student_user_id == data.student_user_id,
                    Certificate.course_id == data.course_id,
                    Certificate.status == CertificateStatus.ISSUED,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return CertificateResponse(
                message="Certificate already issued.",
                certificate=_out(existing, settings),
            )
        raise ConflictError("Unable to issue certificate")
    await db.commit()
    return CertificateResponse(
        message="Certificate issued successfully.",
        certificate=_out(cert, settings),
    )

@router.get(
    "/certificates",
    response_model=CertificateListResponse,
    summary="List certificates",
    description="Students: their own. Institution staff and heads: their students'. Exam managers: all.",
    responses=errors(*AUTHENTICATED),
)
async def list_certificates(query: Annotated[CertificateQuery, Query()], auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> CertificateListResponse:
    rows, total, exact = await CertificateService(db, settings).list_certificates(
        auth, course_id=query.course_id, student_user_id=query.user_id, status=query.status, pdf_status=query.pdf_status,
        page=query.page, per_page=query.per_page, ascending=query.sort_order == SortOrder.ASC,
    )
    return CertificateListResponse(
        message="Certificates retrieved successfully.",
        certificates=[_out(c, settings) for c in rows],
        page_context=PageContext.build(page=query.page, per_page=query.per_page, total=total, is_exact=exact, sort_column="issued_time", sort_order=query.sort_order),
    )


class CertificateExportQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: id_field("course_id", "1755000000001001") | None = None  # type: ignore[valid-type]
    status: CertificateStatus | None = None


_EXPORT_COLUMNS = ("certificate_id", "verification_code", "verification_url", "student_name", "institution", "course", "completion_date", "score_percent", "grade", "status", "issued_at", "revoked_at")
_EXPORT_MAX_ROWS = 10_000


@router.get(
    "/certificates/export",
    response_class=StreamingResponse,
    summary="Export certificates (CSV, staff)",
    description="The same certificates the list shows this person (institution staff: their students'; exam managers: all), "
    f"filtered by course and status, as CSV. At most {_EXPORT_MAX_ROWS:,} rows, newest first.",
    responses={200: {"content": {"text/csv": {}}}, **errors(*AUTHENTICATED, 403)},
)
async def export_certificates(query: Annotated[CertificateExportQuery, Query()], auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> StreamingResponse:
    if not (can_manage_certificates(auth) or is_institution_staff(auth, "export")):
        raise PermissionDeniedError()
    rows, _, _ = await CertificateService(db, settings).list_certificates(
        auth, course_id=query.course_id, student_user_id=None, status=query.status, pdf_status=None, page=1, per_page=_EXPORT_MAX_ROWS, ascending=False,
    )

    def lines() -> Iterator[str]:
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(_EXPORT_COLUMNS)
        for c in rows:
            writer.writerow([
                str(c.public_id), c.verification_code, verification_url(settings, c.verification_code), c.student_name or "", c.institution_name or "",
                c.course_title or "", c.completion_date.date().isoformat(), f"{c.score_percent:.1f}", c.grade_label or "", c.status,
                c.issued_at.isoformat(), c.revoked_at.isoformat() if c.revoked_at else "",
            ])
            yield out.getvalue()
            out.seek(0)
            out.truncate(0)
        if not rows:
            yield out.getvalue()

    return StreamingResponse(
        ("﻿" + chunk if i == 0 else chunk for i, chunk in enumerate(lines())),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="certificates.csv"', "Cache-Control": "private, no-store"},
    )


@router.get(
    "/certificates/{certificate_id}",
    response_model=CertificateResponse,
    summary="Get a certificate",
    description="Includes the public verification URL and a LinkedIn \"Add to profile\" link. `pdf_status` is `pending` "
    "until the worker has rendered it.",
    responses=errors(*AUTHENTICATED, 404),
)
async def get_certificate(certificate_id: CertificateIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> CertificateResponse:
    certificate = await CertificateService(db, settings).get(certificate_id, auth)
    return CertificateResponse(message="Certificate retrieved successfully.", certificate=_out(certificate, settings))


@router.get(
    "/certificates/{certificate_id}/download",
    response_model=DownloadResponse,
    dependencies=[DownloadRateLimit],
    summary="A short-lived link to the certificate PDF",
    description="409 `PDF_NOT_READY` while it is still being rendered. A revoked certificate's PDF is no longer given to the student.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def download_certificate(certificate_id: CertificateIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> DownloadResponse:
    service = CertificateService(db, settings)
    certificate = await service.get(certificate_id, auth)
    if certificate.student_user_id == auth.user_id and not is_student(auth, "export"):
        raise PermissionDeniedError("Downloading your certificates is turned off for your account.")
    url, filename = await service.download(certificate, auth)
    return DownloadResponse(message="Download link issued.", download=DownloadOut(url=url, filename=filename, expires_in=settings.S3_DOWNLOAD_URL_EXPIRES_SECONDS))


@router.post(
    "/certificates/{certificate_id}/revoke",
    response_model=StaffCertificateResponse,
    summary="Revoke a certificate",
    description="Needs `exams.manage`. The public verification page then shows it as revoked. Integrity cases revoke "
    "automatically (`course.pass_revoked`); this is for everything else. Emits `certificate.revoked`.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def revoke_certificate(certificate_id: CertificateIdParam, data: RevokeIn, auth: RequireCertificateManager, db: DbSession, settings: SettingsDep) -> StaffCertificateResponse:
    service = CertificateService(db, settings)
    certificate = await IssueService(db, settings).revoke_by_manager(await service.get(certificate_id, auth), data.reason, auth.user_id)
    return StaffCertificateResponse(message="Certificate revoked.", certificate=_staff_out(certificate, settings))


@router.post(
    "/certificates/{certificate_id}/regenerate-pdf",
    response_model=StaffCertificateResponse,
    summary="Render the PDF again",
    description="For a PDF that failed or whose details arrived late. The same content produces the same file.",
    responses=errors(*AUTHENTICATED, 404),
)
async def regenerate_pdf(certificate_id: CertificateIdParam, auth: RequireCertificateManager, db: DbSession, settings: SettingsDep) -> StaffCertificateResponse:
    service = CertificateService(db, settings)
    certificate = await service.regenerate(await service.get(certificate_id, auth), auth.user_id)
    return StaffCertificateResponse(message="The PDF will be regenerated shortly.", certificate=_staff_out(certificate, settings))


@router.get(
    "/certificates/{certificate_id}/details",
    response_model=StaffCertificateResponse,
    summary="A certificate with its operational details (staff)",
    responses=errors(*AUTHENTICATED, 403, 404),
)
async def certificate_details(certificate_id: CertificateIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> StaffCertificateResponse:
    if not (can_manage_certificates(auth) or is_institution_staff(auth)):
        raise PermissionDeniedError()
    certificate = await CertificateService(db, settings).get(certificate_id, auth)
    return StaffCertificateResponse(message="Certificate retrieved successfully.", certificate=_staff_out(certificate, settings))


@router.get("/certificates/{certificate_id}/events", response_model=EventsResponse, summary="A certificate's audit trail (staff)", responses=errors(*AUTHENTICATED, 403, 404))
async def certificate_events(certificate_id: CertificateIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> EventsResponse:
    if not (can_manage_certificates(auth) or is_institution_staff(auth)):
        raise PermissionDeniedError()
    service = CertificateService(db, settings)
    events = await service.events(await service.get(certificate_id, auth))
    return EventsResponse(message="Events retrieved successfully.", events=[EventOut.model_validate(e) for e in events])


@router.get(
    "/public/verify/{code}",
    response_model=VerificationResponse,
    dependencies=[PublicVerifyRateLimit],
    tags=["Public"],
    summary="Verify a certificate (no login)",
    description="What the QR code on a certificate leads to. Anyone can call it; it reveals only what is printed on the "
    "certificate and whether it is still valid or has been revoked (never why). Rate limited per IP.",
    responses={404: errors(404)[404], 429: errors(429)[429]},
)
async def verify_certificate(code: str, db: DbSession, settings: SettingsDep) -> VerificationResponse:
    certificate = await CertificateService(db, settings).get_by_code(code[:64])
    revoked = certificate.status == CertificateStatus.REVOKED
    return VerificationResponse(
        message="This certificate has been revoked." if revoked else "This certificate is valid.",
        verification=VerificationOut(
            valid=not revoked,
            status=certificate.status,
            certificate_id=str(certificate.public_id),
            student_name=certificate.student_name,
            course_title=certificate.course_title,
            institution_name=certificate.institution_name,
            issuer=settings.ISSUER_NAME,
            completion_date=certificate.completion_date,
            grade=certificate.grade_label,
            score_percent=certificate.score_percent,
            issued_at=certificate.issued_at,
            revoked_at=certificate.revoked_at if revoked else None,
        ),
    )
