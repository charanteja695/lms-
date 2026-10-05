from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import Response
from lms_common.envelopes import PageContext, SortOrder
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import (
    AuthoringRateLimit,
    CurrentAuth,
    DbSession,
    RequireTemplateAuthor,
    RequireTemplatePublisher,
    SettingsDep,
    TemplateIdParam,
)
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import PermissionDeniedError
from app.domain.enums import TemplateStatus
from app.permissions.policy import can_author_templates, can_publish_templates
from app.render.pdf import CertificateData, render_pdf
from app.schemas.template import TemplateCreate, TemplateListResponse, TemplateOut, TemplateResponse, TemplateUpdate
from app.schemas.types import id_field
from app.services.template_service import TemplateService, snapshot_of

router = APIRouter(prefix="/certificate-templates", tags=["Templates"])


class TemplateQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: id_field("course_id", "1755000000001001") | None = None  # type: ignore[valid-type]
    status: TemplateStatus | None = None
    page: int = Field(default=1, ge=1, le=10_000)
    per_page: int = Field(default=20, ge=1, le=100)


def _require_reader(auth: CurrentAuth) -> None:
    if not (can_author_templates(auth) or can_publish_templates(auth)):
        raise PermissionDeniedError()


@router.post(
    "",
    response_model=TemplateResponse,
    status_code=201,
    dependencies=[AuthoringRateLimit],
    summary="Create a certificate template (draft)",
    description="`course_id` empty makes the platform default. `body_text` / `footer_text` may use "
    "`{student_name} {course_title} {completion_date} {institution_name} {score_percent} {grade} {issuer} {certificate_id}`; "
    "`grade_bands` map a score to a label (the lowest band must start at 0).",
    responses=errors(*AUTHENTICATED),
)
async def create_template(data: TemplateCreate, auth: RequireTemplateAuthor, db: DbSession) -> TemplateResponse:
    template = await TemplateService(db).create(data, auth)
    return TemplateResponse(message="Template created successfully.", template=TemplateOut.model_validate(template))


@router.get("", response_model=TemplateListResponse, summary="List templates", responses=errors(*AUTHENTICATED))
async def list_templates(query: Annotated[TemplateQuery, Query()], auth: CurrentAuth, db: DbSession) -> TemplateListResponse:
    _require_reader(auth)
    rows, total, exact = await TemplateService(db).list_templates(course_id=query.course_id, status=query.status, page=query.page, per_page=query.per_page)
    return TemplateListResponse(
        message="Templates retrieved successfully.",
        templates=[TemplateOut.model_validate(t) for t in rows],
        page_context=PageContext.build(page=query.page, per_page=query.per_page, total=total, is_exact=exact, sort_column="created_time", sort_order=SortOrder.DESC),
    )


@router.get("/{template_id}", response_model=TemplateResponse, summary="Get a template", responses=errors(*AUTHENTICATED, 404))
async def get_template(template_id: TemplateIdParam, auth: CurrentAuth, db: DbSession) -> TemplateResponse:
    _require_reader(auth)
    return TemplateResponse(message="Template retrieved successfully.", template=TemplateOut.model_validate(await TemplateService(db).get(template_id)))


@router.patch("/{template_id}", response_model=TemplateResponse, dependencies=[AuthoringRateLimit], summary="Edit a draft template", responses=errors(*AUTHENTICATED, 404, 409))
async def update_template(template_id: TemplateIdParam, data: TemplateUpdate, auth: RequireTemplateAuthor, db: DbSession) -> TemplateResponse:
    service = TemplateService(db)
    template = await service.update(await service.get(template_id), data)
    return TemplateResponse(message="Template updated successfully.", template=TemplateOut.model_validate(template))


@router.post(
    "/{template_id}/activate",
    response_model=TemplateResponse,
    summary="Make a template the one used for new certificates",
    description="Needs `content.review`. Replaces (archives) the template active for the same course. Certificates already "
    "issued keep the template they were issued with.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def activate_template(template_id: TemplateIdParam, auth: RequireTemplatePublisher, db: DbSession) -> TemplateResponse:
    service = TemplateService(db)
    template = await service.activate(await service.get(template_id))
    return TemplateResponse(message="Template activated.", template=TemplateOut.model_validate(template))


@router.post("/{template_id}/archive", response_model=TemplateResponse, summary="Archive a template", responses=errors(*AUTHENTICATED, 404))
async def archive_template(template_id: TemplateIdParam, auth: RequireTemplatePublisher, db: DbSession) -> TemplateResponse:
    service = TemplateService(db)
    template = await service.archive(await service.get(template_id))
    return TemplateResponse(message="Template archived.", template=TemplateOut.model_validate(template))


@router.get(
    "/{template_id}/preview",
    summary="Render a sample certificate with this template (PDF)",
    responses={**errors(*AUTHENTICATED, 404), 200: {"content": {"application/pdf": {}}, "description": "A sample PDF"}},
)
async def preview_template(template_id: TemplateIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> Response:
    _require_reader(auth)
    template = await TemplateService(db).get(template_id)
    sample = CertificateData(
        certificate_id="360471859873173362", student_name="Aarav Reddy", course_title="Full Stack Development with MERN",
        institution_name="Springfield High", completion_date="21 September 2026", score_percent="91.5", grade="Distinction",
        issuer=settings.ISSUER_NAME, verification_url=f"{settings.PUBLIC_VERIFY_BASE_URL.rstrip('/')}/SAMPLE", verification_code="SAMPLE",
        template=snapshot_of(template),
    )
    return Response(render_pdf(sample), media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="preview.pdf"'})
