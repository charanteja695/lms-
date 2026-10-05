from fastapi import APIRouter

from app.api.deps import DbSession, RequireSuperAdmin, WriteRateLimit
from app.api.responses import errors
from app.domain.enums import Channel
from app.schemas.template import TemplateListResponse, TemplateOut, TemplateResponse, TemplateUpdate
from app.services.template_service import TemplateService

router = APIRouter(prefix="/notification-templates", tags=["Templates"])


@router.get("", response_model=TemplateListResponse, summary="List every notification template", responses=errors(401, 403, 429))
async def list_templates(auth: RequireSuperAdmin, db: DbSession) -> TemplateListResponse:
    views = await TemplateService(db).list_all()
    return TemplateListResponse(
        message="Templates retrieved successfully.", templates=[TemplateOut.model_validate(view) for view in views]
    )


@router.put(
    "/{type_key}/{channel}",
    response_model=TemplateResponse,
    summary="Override the wording of a notification",
    responses=errors(401, 403, 404, 422, 429),
    dependencies=[WriteRateLimit],
)
async def update_template(type_key: str, channel: Channel, data: TemplateUpdate, auth: RequireSuperAdmin, db: DbSession) -> TemplateResponse:
    view = await TemplateService(db).upsert(auth.user_id, type_key, channel, subject=data.subject, body=data.body)
    return TemplateResponse(message="Template saved successfully.", template=TemplateOut.model_validate(view))


@router.delete(
    "/{type_key}/{channel}",
    response_model=TemplateResponse,
    summary="Reset a notification to its default wording",
    responses=errors(401, 403, 404, 429),
    dependencies=[WriteRateLimit],
)
async def reset_template(type_key: str, channel: Channel, auth: RequireSuperAdmin, db: DbSession) -> TemplateResponse:
    view = await TemplateService(db).reset(type_key, channel)
    return TemplateResponse(message="Template reset to the default.", template=TemplateOut.model_validate(view))
