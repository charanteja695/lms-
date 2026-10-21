from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder
from lms_common.pagination import paginate
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import CaseIdParam, CurrentAuth, DbSession, RequireExamManager, SettingsDep, SnapshotIdParam
from app.api.responses import AUTHENTICATED, errors
from app.api.titles import test_titles
from app.clients.assessment import AssessmentClient
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.domain.enums import CaseStatus
from app.models.case import IntegrityCase
from app.models.session import MediaAccess, ProctorSession, Snapshot
from app.permissions.policy import can_manage_exams, is_employer_member, is_institution_staff
from app.schemas.proctoring import (
    AppealDecisionIn,
    CaseDetailOut,
    CaseDetailResponse,
    CaseListResponse,
    CaseOut,
    CaseResponse,
    DecideIn,
    MediaAccessOut,
    MediaAccessResponse,
    MediaUrlResponse,
    SnapshotOut,
)
from app.schemas.types import id_field
from app.services.case_service import CaseService
from app.services.snapshot_service import SnapshotService

router = APIRouter(tags=["Integrity review"])


class CaseQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_id: id_field("test_id", "1755000000000555") | None = None  # type: ignore[valid-type]
    status: CaseStatus | None = None
    overdue: bool | None = None
    page: int = Field(default=1, ge=1, le=10_000)
    per_page: int = Field(default=20, ge=1, le=100)


def _out(case: IntegrityCase, service: CaseService) -> CaseOut:
    out = CaseOut.model_validate(case)
    out.overdue, out.can_appeal = service.overdue(case), service.can_appeal(case)
    return out


async def _deliver(settings: SettingsDep, case: IntegrityCase, decision: str) -> None:
    """Also tell assessment-service directly (the synchronous twin of the event): the shared consumer does not redeliver an
    event whose handler raised, so an integrity decision must not depend on the event alone. Best effort: the event is
    already committed to the outbox, and assessment applies a repeated decision idempotently."""
    import logging

    from app.clients.assessment import AssessmentRejected, AssessmentUnavailable

    try:
        await AssessmentClient(settings).integrity(case.attempt_id, decision)
    except (AssessmentUnavailable, AssessmentRejected) as exc:
        logging.getLogger(__name__).warning("Direct integrity push for attempt %s failed (%s); the event will carry it", case.attempt_id, exc)


@router.get(
    "/cases",
    response_model=CaseListResponse,
    summary="Integrity cases to review",
    description="Newest first. Exam managers see all; institution staff their own students' (platform tests); an employer's "
    "members the cases of its hiring assessments. `overdue` marks cases nobody has decided within the configured window "
    "(never decided automatically).",
    responses=errors(*AUTHENTICATED),
)
async def list_cases(query: Annotated[CaseQuery, Query()], auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> CaseListResponse:
    stmt = select(IntegrityCase)
    if can_manage_exams(auth):
        pass
    elif is_employer_member(auth):
        stmt = stmt.where(IntegrityCase.test_owner_id == auth.organization_id)
    elif is_institution_staff(auth):
        stmt = stmt.where(IntegrityCase.organization_id == auth.organization_id, IntegrityCase.test_owner_id.is_(None))
    else:
        raise PermissionDeniedError()
    if query.test_id:
        stmt = stmt.where(IntegrityCase.test_id == query.test_id)
    if query.status:
        stmt = stmt.where(IntegrityCase.status == query.status)
    service = CaseService(db, settings)
    rows, total, exact = await paginate(db, stmt.order_by(IntegrityCase.created_at.desc(), IntegrityCase.id), query.page, query.per_page)
    titles = await test_titles(db, (c.test_id for c in rows))
    cases = [_out(c, service).model_copy(update={"test_title": titles.get(c.test_id)}) for c in rows]
    if query.overdue is not None:
        cases = [c for c in cases if c.overdue == query.overdue]
    return CaseListResponse(
        message="Cases retrieved successfully.", cases=cases,
        page_context=PageContext.build(page=query.page, per_page=query.per_page, total=total, is_exact=exact, sort_column="created_time", sort_order=SortOrder.DESC),
    )


@router.get(
    "/cases/{case_id}",
    response_model=CaseDetailResponse,
    summary="A case with its integrity report and snapshots",
    description="The report has the risk breakdown, the timeline, event counts and `ai_analysis` (`complete`, `partial`, "
    "`unavailable` or `not_applicable`: a report never reads as 'looked and found nothing' when nothing was analysed). "
    "Snapshot images are fetched one at a time from `/cases/{id}/snapshots/{snapshot_id}/url`, and each is logged.",
    responses=errors(*AUTHENTICATED, 404),
)
async def get_case(case_id: CaseIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> CaseDetailResponse:
    service = CaseService(db, settings)
    case = await service.get_for_reviewer(case_id, auth)
    snapshots = (await db.execute(select(Snapshot).where(Snapshot.session_id == case.session_id).order_by(Snapshot.taken_at).limit(500))).scalars()
    out = _out(case, service)
    out.test_title = (await test_titles(db, [case.test_id])).get(case.test_id)
    detail = CaseDetailOut.model_construct(  # the raw values under their field names (the ORM attributes carry aliases)
        **{name: getattr(out, name) for name in CaseOut.model_fields}, report=case.report, snapshots=[SnapshotOut.model_validate(s) for s in snapshots]
    )
    return CaseDetailResponse(message="Case retrieved successfully.", case=detail)


@router.get(
    "/cases/{case_id}/snapshots/{snapshot_id}/url",
    response_model=MediaUrlResponse,
    summary="A short-lived link to one snapshot (audited)",
    description="Every call is logged with who asked and why (`GET /audit/media-access`); media past its retention is gone (404 `MEDIA_DELETED`).",
    responses=errors(*AUTHENTICATED, 404),
)
async def snapshot_url(case_id: CaseIdParam, snapshot_id: SnapshotIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> MediaUrlResponse:
    case = await CaseService(db, settings).get_for_reviewer(case_id, auth)
    snapshot = (await db.execute(select(Snapshot).where(Snapshot.public_id == snapshot_id, Snapshot.session_id == case.session_id))).scalar_one_or_none()
    if snapshot is None:
        raise NotFoundError("Snapshot not found.", code="SNAPSHOT_NOT_FOUND")
    url = await SnapshotService(db, settings).view_url(snapshot, auth.user_id, "case_review")
    return MediaUrlResponse(message="Link issued.", url=url, expires_in=settings.S3_DOWNLOAD_URL_EXPIRES_SECONDS)


@router.post("/cases/{case_id}/claim", response_model=CaseResponse, summary="Take a case for review", responses=errors(*AUTHENTICATED, 404, 409))
async def claim_case(case_id: CaseIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> CaseResponse:
    service = CaseService(db, settings)
    case = await service.claim(await service.get_for_reviewer(case_id, auth, lock=True), auth)
    return CaseResponse(message="Case claimed.", case=_out(case, service))


@router.post(
    "/cases/{case_id}/decide",
    response_model=CaseResponse,
    summary="Decide a case: reviewed_ok or invalidated",
    description="A person always confirms an invalidation and must give a written `note`. Emits `integrity.decided` (and "
    "tells assessment-service directly). The student may appeal an invalidation once.",
    responses=errors(*AUTHENTICATED, 404, 409, 422),
)
async def decide_case(case_id: CaseIdParam, data: DecideIn, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> CaseResponse:
    service = CaseService(db, settings)
    case = await service.decide(await service.get_for_reviewer(case_id, auth, lock=True), auth, data.decision, data.note)
    await _deliver(settings, case, data.decision)
    return CaseResponse(message="Decision recorded.", case=_out(case, service))


@router.post(
    "/cases/{case_id}/decide-appeal",
    response_model=CaseResponse,
    summary="Decide an appeal: upheld or overturned",
    description="Exam managers only, and never the reviewer who made the original decision. Overturning emits "
    "`integrity.decided` with `reviewed_ok`.",
    responses=errors(*AUTHENTICATED, 403, 404, 409, 422),
)
async def decide_appeal(case_id: CaseIdParam, data: AppealDecisionIn, auth: RequireExamManager, db: DbSession, settings: SettingsDep) -> CaseResponse:
    service = CaseService(db, settings)
    case = await service.decide_appeal(await service.get_for_reviewer(case_id, auth, lock=True), auth, data.outcome, data.note)
    if data.outcome == "overturned":
        await _deliver(settings, case, "reviewed_ok")
    return CaseResponse(message="Appeal decided.", case=_out(case, service))


@router.get(
    "/audit/media-access",
    response_model=MediaAccessResponse,
    summary="Who viewed whose snapshots",
    description="Exam managers only. Snapshots are access-controlled and every view is logged (docs/PRODUCT.md §5.3).",
    responses=errors(*AUTHENTICATED),
)
async def media_access(auth: RequireExamManager, db: DbSession, page: int = Query(default=1, ge=1, le=10_000), per_page: int = Query(default=50, ge=1, le=200)) -> MediaAccessResponse:
    stmt = (
        select(MediaAccess, Snapshot.public_id, ProctorSession.public_id)
        .join(Snapshot, Snapshot.id == MediaAccess.snapshot_id)
        .join(ProctorSession, ProctorSession.id == MediaAccess.session_id)
        .order_by(MediaAccess.created_at.desc())
        .limit(per_page)
        .offset((page - 1) * per_page)
    )
    rows = (await db.execute(stmt)).all()
    return MediaAccessResponse(
        message="Access log retrieved successfully.",
        accesses=[MediaAccessOut(snapshot_id=snap, session_id=sess, viewer_user_id=a.viewer_user_id, reason=a.reason, created_at=a.created_at) for a, snap, sess in rows],
        page_context=PageContext.build(page=page, per_page=per_page, total=len(rows), is_exact=False, sort_column="created_time", sort_order=SortOrder.DESC),
    )

