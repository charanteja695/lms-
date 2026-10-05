"""AI assistance (through ai-gateway) and exports. AI answers are suggestions checked against the student's own facts; nothing is saved."""

import json
from typing import Any

from fastapi import APIRouter, Response

from app.api.deps import (
    AiRateLimit,
    DbSession,
    ExportRateLimit,
    GatewayDep,
    PublicRateLimit,
    RequireStudent,
    ResumeIdParam,
    SettingsDep,
    WriteRateLimit,
)
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import ValidationFailedError
from app.models.resume import Resume
from app.rendering.jsonresume import to_json_resume
from app.rendering.pdf import render_pdf
from app.schemas.resume import (
    RewriteRequest,
    ShareOut,
    ShareRequest,
    ShareResponse,
    SuggestionResponse,
    SuggestionsResponse,
    SummaryRequest,
    TailorRequest,
    TextRequest,
)
from app.services.ai_service import AiService, gap_report
from app.services.resume_service import ResumeService

router = APIRouter(tags=["Resumes: AI and export"])
public = APIRouter(prefix="/public", tags=["Public share"], dependencies=[PublicRateLimit])

_AI = "The result is a **suggestion**: anything it says that is not in your profile (a number, a name, a link, a keyword you do not have) is listed in `warnings` and `applicable` is false. Nothing is saved; apply a suggestion by editing your resume."


@router.post("/resumes/{resume_id}/ai/summary", response_model=SuggestionResponse, summary="Suggest a summary", description=_AI, responses=errors(*AUTHENTICATED, 404, 503), dependencies=[AiRateLimit])
async def ai_summary(resume_id: ResumeIdParam, body: SummaryRequest, auth: RequireStudent, db: DbSession, settings: SettingsDep, gateway: GatewayDep) -> SuggestionResponse:
    service = ResumeService(db, settings)
    resume = await service.get(auth.user_id, resume_id)
    profile = await service.profiles.get(auth.user_id)
    views = await service.profiles.views(auth.user_id)
    await db.commit()  # no transaction is held open across the model call
    suggestion = await AiService(settings, gateway).summary(
        organization_id=auth.organization_id, user_id=auth.user_id, views=views, profile_summary=profile.summary if profile else None, target_role=resume.target_role, tone=body.tone
    )
    return SuggestionResponse(message="", suggestion=suggestion)


@router.post("/resumes/{resume_id}/ai/rewrite", response_model=SuggestionsResponse, summary="Rewrite bullets with impact", description=_AI, responses=errors(*AUTHENTICATED, 404, 503), dependencies=[AiRateLimit])
async def ai_rewrite(resume_id: ResumeIdParam, body: RewriteRequest, auth: RequireStudent, db: DbSession, settings: SettingsDep, gateway: GatewayDep) -> SuggestionsResponse:
    await ResumeService(db, settings).get(auth.user_id, resume_id)
    await db.commit()
    results = await AiService(settings, gateway).rewrite(organization_id=auth.organization_id, user_id=auth.user_id, bullets=body.bullets, context=body.context)
    return SuggestionsResponse(message="", suggestions=results)


@router.post("/resumes/{resume_id}/ai/polish", response_model=SuggestionResponse, summary="Correct grammar and tone of a text", description=_AI, responses=errors(*AUTHENTICATED, 404, 503), dependencies=[AiRateLimit])
async def ai_polish(resume_id: ResumeIdParam, body: TextRequest, auth: RequireStudent, db: DbSession, settings: SettingsDep, gateway: GatewayDep) -> SuggestionResponse:
    await ResumeService(db, settings).get(auth.user_id, resume_id)
    await db.commit()
    return SuggestionResponse(message="", suggestion=await AiService(settings, gateway).polish(organization_id=auth.organization_id, user_id=auth.user_id, text=body.text, tone=body.tone))


@router.post(
    "/resumes/{resume_id}/ai/tailor", response_model=SuggestionResponse, summary="Tailor to a job description",
    description="The keyword gap (rule-based) for the job, and optionally a summary that leans on the keywords your facts support. " + _AI, responses=errors(*AUTHENTICATED, 404, 422, 503), dependencies=[AiRateLimit],
)
async def ai_tailor(resume_id: ResumeIdParam, body: TailorRequest, auth: RequireStudent, db: DbSession, settings: SettingsDep, gateway: GatewayDep) -> SuggestionResponse:
    service = ResumeService(db, settings)
    resume = await service.get(auth.user_id, resume_id)
    job = body.job_description or resume.job_description
    if not job:
        raise ValidationFailedError(details=[{"field": "job_description", "code": "REQUIRED", "message": "Send a job description, or save one on the resume"}])
    document, _ = await service.document(resume)
    profile = await service.profiles.get(auth.user_id)
    views = await service.profiles.views(auth.user_id)
    gap = gap_report(job, document, views, profile.summary if profile else None)
    result: dict[str, object] = {"gap": gap, "summary": None}
    role, org = resume.target_role, auth.organization_id
    await db.commit()
    if body.include_summary:
        terms = [str(k["term"]) for k in gap["keywords"]]
        result["summary"] = await AiService(settings, gateway).tailor_summary(
            organization_id=org, user_id=auth.user_id, views=views, profile_summary=profile.summary if profile else None, target_role=role, keywords=terms
        )
    return SuggestionResponse(message="", suggestion=result)


# ---------------------------------------------------------------- export
async def _document_for(service: ResumeService, resume: Resume, version_no: int | None) -> tuple[dict[str, Any], dict[str, dict[str, Any]], str]:
    if version_no is None:
        document, raw = await service.document(resume)
        return document, raw, resume.template_key
    version = await service.version(resume, version_no)
    _, raw = await service.document(resume)
    return version.document, raw, version.template_key


@router.get(
    "/resumes/{resume_id}/export/pdf", summary="Download as PDF", response_class=Response, responses={200: {"content": {"application/pdf": {}}, "description": "The PDF"}, **errors(*AUTHENTICATED, 404)},
    description="Server-rendered with the resume's template, from the current draft or from a saved `version_no`. The PDF uses standard fonts: characters outside "
    "Latin-1 (for example Devanagari) print as `?`, and `X-Unrenderable-Characters` says how many.", dependencies=[ExportRateLimit],
)
async def export_pdf(resume_id: ResumeIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep, version_no: int | None = None) -> Response:
    service = ResumeService(db, settings)
    resume = await service.get(auth.user_id, resume_id)
    document, _, template_key = await _document_for(service, resume, version_no)
    template = await service.template(template_key)
    pdf, lost = render_pdf(document, template.config, title=resume.title)
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in resume.title)[:60] or "resume"
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{safe}.pdf"', "X-Unrenderable-Characters": str(lost), "Cache-Control": "private, no-store"})


@router.get("/resumes/{resume_id}/export/json-resume", summary="Download as JSON Resume", responses=errors(*AUTHENTICATED, 404), dependencies=[ExportRateLimit])
async def export_json(resume_id: ResumeIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep, version_no: int | None = None) -> Response:
    service = ResumeService(db, settings)
    resume = await service.get(auth.user_id, resume_id)
    document, raw, _ = await _document_for(service, resume, version_no)
    body = json.dumps(to_json_resume(document, raw_items=raw), ensure_ascii=False, indent=2)
    return Response(content=body, media_type="application/json", headers={"Content-Disposition": 'attachment; filename="resume.json"', "Cache-Control": "private, no-store"})


# ---------------------------------------------------------------- sharing
@router.post(
    "/resumes/{resume_id}/share", response_model=ShareResponse, summary="Create a public share link",
    description="Pins the link to a saved version (a fresh snapshot of the draft by default), so later edits never change what was sent. Sharing again replaces the previous link. "
    "Contact details are hidden unless `show_contact`. The link expires (30 days by default) and can be revoked.", responses=errors(*AUTHENTICATED, 404), dependencies=[WriteRateLimit],
)
async def share(resume_id: ResumeIdParam, body: ShareRequest, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> ShareResponse:
    service = ResumeService(db, settings)
    resume = await service.share(await service.get(auth.user_id, resume_id), version_no=body.version_no, expires_in_days=body.expires_in_days, show_contact=body.show_contact)
    if not resume.share_token or resume.share_version_no is None:
        raise RuntimeError("share() did not set the link")
    return ShareResponse(
        message="Link created.",
        share=ShareOut(token=resume.share_token, url_path=f"/api/v1/public/resumes/{resume.share_token}", version_no=resume.share_version_no, expires_at=resume.share_expires_at, show_contact=resume.share_show_contact),
    )


@router.delete("/resumes/{resume_id}/share", summary="Revoke the public link", status_code=204, responses=errors(*AUTHENTICATED, 404), dependencies=[WriteRateLimit])
async def unshare(resume_id: ResumeIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> Response:
    service = ResumeService(db, settings)
    await service.unshare(await service.get(auth.user_id, resume_id))
    return Response(status_code=204)


_NO_INDEX = {"X-Robots-Tag": "noindex, nofollow", "Cache-Control": "private, max-age=60", "Referrer-Policy": "no-referrer"}


@public.get("/resumes/{token}", summary="A shared resume as JSON Resume", description="No login. An unknown, revoked, expired or deleted link is one and the same `404 SHARE_NOT_FOUND`.", responses=errors(404, 429))
async def public_resume(token: str, db: DbSession, settings: SettingsDep) -> Response:
    service = ResumeService(db, settings)
    resume, version = await service.public(token)
    document = service.public_document(version.document, show_contact=resume.share_show_contact)
    _, raw = await service.document(resume)
    body = json.dumps({"resume": to_json_resume(document, raw_items=raw), "document": document, "version_no": version.version_no}, ensure_ascii=False)
    return Response(content=body, media_type="application/json", headers=_NO_INDEX)


@public.get("/resumes/{token}/pdf", summary="A shared resume as PDF", response_class=Response, responses={200: {"content": {"application/pdf": {}}, "description": "The PDF"}, **errors(404, 429)})
async def public_pdf(token: str, db: DbSession, settings: SettingsDep) -> Response:
    service = ResumeService(db, settings)
    resume, version = await service.public(token)
    document = service.public_document(version.document, show_contact=resume.share_show_contact)
    template = await service.template(version.template_key)
    pdf, _ = render_pdf(document, template.config, title=resume.title)
    return Response(content=pdf, media_type="application/pdf", headers={**_NO_INDEX, "Content-Disposition": 'inline; filename="resume.pdf"'})

