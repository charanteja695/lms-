"""Resumes: create and edit, versions, ATS score and fixes, keyword gap, grammar check, templates."""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import DbSession, RequireStudent, ResumeIdParam, SettingsDep, WriteRateLimit
from app.api.responses import AUTHENTICATED, errors
from app.ats.language import check_text
from app.core.exceptions import ValidationFailedError
from app.models.resume import Resume, ResumeVersion
from app.schemas.resume import (
    AtsRequest,
    AtsResponse,
    GrammarResponse,
    ResumeCreate,
    ResumeDetail,
    ResumeOut,
    ResumePage,
    ResumeResponse,
    ResumeUpdate,
    TemplateOut,
    TemplatesResponse,
    VersionCreate,
    VersionDetail,
    VersionOut,
    VersionResponse,
    VersionsResponse,
)
from app.services.ai_service import gap_report
from app.services.resume_service import ResumeService

router = APIRouter(tags=["Resumes"])


def present_resume(resume: Resume) -> ResumeOut:
    out = ResumeOut.model_validate(resume)
    return out.model_copy(update={"shared": bool(resume.share_token), "share_expires_at": resume.share_expires_at})


def present_version(version: ResumeVersion) -> VersionOut:
    return VersionOut.model_validate(version)


@router.get("/resume-templates", response_model=TemplatesResponse, summary="Resume templates", description="Every template is single-column plain text with standard headings, so an applicant tracking system reads it in order.", responses=errors(*AUTHENTICATED))
async def templates(_: RequireStudent, db: DbSession, settings: SettingsDep) -> TemplatesResponse:
    return TemplatesResponse(message="", templates=[TemplateOut.model_validate(t) for t in await ResumeService(db, settings).templates()])


@router.get("/resumes", response_model=ResumePage, summary="My resumes", responses=errors(*AUTHENTICATED))
async def list_resumes(
    auth: RequireStudent, db: DbSession, settings: SettingsDep, page: Annotated[int, Query(ge=1, le=1_000)] = 1, per_page: Annotated[int, Query(ge=1, le=50)] = 20
) -> ResumePage:
    rows, total = await ResumeService(db, settings).list_for(auth.user_id, page=page, per_page=per_page)
    context = PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="updated_at", sort_order=SortOrder.DESC)
    return ResumePage(message="", resumes=[present_resume(r) for r in rows], page_context=context)


@router.post(
    "/resumes", response_model=ResumeResponse, status_code=201, summary="Create a resume",
    description="Starts from everything in the profile (education, projects, experience, skills, certificates…) in a sensible order, unless `blank`. "
    "Keep one resume per target role.", responses=errors(*AUTHENTICATED, 409), dependencies=[WriteRateLimit],
)
async def create_resume(body: ResumeCreate, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> ResumeResponse:
    resume = await ResumeService(db, settings).create(
        auth.user_id, auth.organization_id, title=body.title, target_role=body.target_role, template_key=body.template_key, job_description=body.job_description, blank=body.blank
    )
    return ResumeResponse(message="Resume created.", resume=present_resume(resume))


@router.get(
    "/resumes/{resume_id}", response_model=ResumeDetail, summary="A resume: its draft, the document it resolves to now, and its ATS score",
    description="`draft` is what you edit (send its `draft_revision` back as `expected_revision`). `document` is what a reader sees: verified entries are marked "
    "`verified: true`, entries deleted from the profile or revoked are gone.", responses=errors(*AUTHENTICATED, 404),
)
async def get_resume(resume_id: ResumeIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> ResumeDetail:
    service = ResumeService(db, settings)
    resume = await service.get(auth.user_id, resume_id)
    document, _ = await service.document(resume)
    report = await service.ats(resume, job_description=None, document=document)
    return ResumeDetail(
        message="", resume=present_resume(resume), job_description=resume.job_description, draft=resume.draft, document=document, ats=report.as_dict()
    )


@router.patch(
    "/resumes/{resume_id}", response_model=ResumeResponse, summary="Edit a resume",
    description="Send the `draft_revision` you loaded as `expected_revision`: if the resume changed since (another tab), `409 STALE_DRAFT`. Sections are reordered "
    "by the order of `draft.sections`; items by the order of each section's `items`. A section may only hold items of its own kind, and only your own entries can carry "
    "their own `bullets`.", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit],
)
async def update_resume(resume_id: ResumeIdParam, body: ResumeUpdate, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> ResumeResponse:
    service = ResumeService(db, settings)
    resume = await service.get(auth.user_id, resume_id)
    updated = await service.update(
        resume, expected_revision=body.expected_revision, title=body.title, target_role=body.target_role, template_key=body.template_key,
        job_description=body.job_description, draft=body.draft.model_dump(mode="json") if body.draft else None,
    )
    return ResumeResponse(message="Saved.", resume=present_resume(updated))


@router.post("/resumes/{resume_id}/duplicate", response_model=ResumeResponse, status_code=201, summary="Copy a resume (for another target role)", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit])
async def duplicate(resume_id: ResumeIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> ResumeResponse:
    service = ResumeService(db, settings)
    source = await service.get(auth.user_id, resume_id)
    return ResumeResponse(message="Resume copied.", resume=present_resume(await service.duplicate(source, title=f"{source.title} (copy)"[:120])))


@router.delete("/resumes/{resume_id}", response_model=ResumeResponse, summary="Delete a resume (its share link stops working at once)", responses=errors(*AUTHENTICATED, 404), dependencies=[WriteRateLimit])
async def delete_resume(resume_id: ResumeIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> ResumeResponse:
    service = ResumeService(db, settings)
    resume = await service.get(auth.user_id, resume_id)
    await service.delete(resume)
    return ResumeResponse(message="Resume deleted.", resume=present_resume(resume))


# ---------------------------------------------------------------- versions
@router.get("/resumes/{resume_id}/versions", response_model=VersionsResponse, summary="Saved versions, newest first", responses=errors(*AUTHENTICATED, 404))
async def versions(resume_id: ResumeIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> VersionsResponse:
    service = ResumeService(db, settings)
    return VersionsResponse(message="", versions=[present_version(v) for v in await service.versions(await service.get(auth.user_id, resume_id))])


@router.post(
    "/resumes/{resume_id}/versions", response_model=VersionResponse, status_code=201, summary="Save a version",
    description="Freezes the draft and the document it resolves to right now, with its ATS score. The newest 50 are kept.", responses=errors(*AUTHENTICATED, 404), dependencies=[WriteRateLimit],
)
async def save_version(resume_id: ResumeIdParam, body: VersionCreate, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> VersionResponse:
    service = ResumeService(db, settings)
    version = await service.create_version(await service.get(auth.user_id, resume_id), label=body.label, note=body.note)
    return VersionResponse(message="Version saved.", version=present_version(version))


@router.get("/resumes/{resume_id}/versions/{version_no}", response_model=VersionDetail, summary="One saved version with its document", responses=errors(*AUTHENTICATED, 404))
async def get_version(resume_id: ResumeIdParam, version_no: int, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> VersionDetail:
    service = ResumeService(db, settings)
    version = await service.version(await service.get(auth.user_id, resume_id), version_no)
    return VersionDetail(message="", version=present_version(version), document=version.document)


@router.post(
    "/resumes/{resume_id}/versions/{version_no}/restore", response_model=ResumeResponse, summary="Restore a version into the draft",
    description="The current draft is saved as a version first, so nothing is lost.", responses=errors(*AUTHENTICATED, 404), dependencies=[WriteRateLimit],
)
async def restore(resume_id: ResumeIdParam, version_no: int, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> ResumeResponse:
    service = ResumeService(db, settings)
    resume = await service.restore(await service.get(auth.user_id, resume_id), version_no)
    return ResumeResponse(message=f"Restored version {version_no}.", resume=present_resume(resume))


# ---------------------------------------------------------------- scoring and checks
@router.post(
    "/resumes/{resume_id}/ats", response_model=AtsResponse, summary="ATS score with the fixes that raise it",
    description="Computed by fixed rules, so the same resume always scores the same. With a job description (the request's, or the one saved on the resume) the score "
    "includes keyword match. `fixes` are ordered most valuable first.", responses=errors(*AUTHENTICATED, 404),
)
async def ats(resume_id: ResumeIdParam, body: AtsRequest, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> AtsResponse:
    service = ResumeService(db, settings)
    resume = await service.get(auth.user_id, resume_id)
    return AtsResponse(message="", ats=(await service.ats(resume, job_description=body.job_description)).as_dict())


@router.post(
    "/resumes/{resume_id}/keyword-gap", response_model=AtsResponse, summary="Keyword gap against a job description",
    description="`add_from_profile` are terms the job wants that your profile already supports but this resume leaves out. `not_in_profile` are terms you have not recorded anywhere: "
    "add them only if they are true.", responses=errors(*AUTHENTICATED, 404, 422),
)
async def keyword_gap(resume_id: ResumeIdParam, body: AtsRequest, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> AtsResponse:
    service = ResumeService(db, settings)
    resume = await service.get(auth.user_id, resume_id)
    job = body.job_description or resume.job_description
    if not job:
        raise ValidationFailedError(details=[{"field": "job_description", "code": "REQUIRED", "message": "Send a job description, or save one on the resume"}])
    document, _ = await service.document(resume)
    profile = await service.profiles.get(auth.user_id)
    views = await service.profiles.views(auth.user_id)
    return AtsResponse(message="", ats=gap_report(job, document, views, profile.summary if profile else None))


@router.post(
    "/resumes/{resume_id}/grammar", response_model=GrammarResponse, summary="Grammar and tone check (rule-based, no AI)",
    description="Repeated words, spacing, first person, weak openings, filler and buzzwords, across the summary and every bullet you wrote.", responses=errors(*AUTHENTICATED, 404),
)
async def grammar(resume_id: ResumeIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> GrammarResponse:
    service = ResumeService(db, settings)
    resume = await service.get(auth.user_id, resume_id)
    document, _ = await service.document(resume)
    issues = []
    if document.get("summary"):
        issues += [{"where": "summary", "item_id": None, "code": i.code, "severity": i.severity, "message": i.message, "excerpt": i.excerpt} for i in check_text(document["summary"])]
    for section in document["sections"]:
        for entry in section["entries"]:
            if entry["verified"]:
                continue  # platform text is not the student's to fix
            for bullet in entry["bullets"]:
                issues += [{"where": section["key"], "item_id": entry["item_id"], "code": i.code, "severity": i.severity, "message": i.message, "excerpt": i.excerpt} for i in check_text(bullet)]
    return GrammarResponse(message="", issues=issues)
