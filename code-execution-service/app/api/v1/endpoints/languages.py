from fastapi import APIRouter

from app.api.deps import CurrentAuth, DbSession, RequireSuperAdmin
from app.api.responses import errors
from app.schemas.language import (
    LanguageAdminListResponse,
    LanguageAdminOut,
    LanguageCreate,
    LanguageListResponse,
    LanguageOut,
    LanguageResponse,
    LanguageUpdate,
)
from app.services.language_service import LanguageService

router = APIRouter(prefix="/languages", tags=["Languages"])


@router.get("", response_model=LanguageListResponse, summary="List the languages the editor can use", responses=errors(401, 429))
async def list_languages(auth: CurrentAuth, db: DbSession) -> LanguageListResponse:
    languages = await LanguageService(db).list_languages()
    return LanguageListResponse(
        message="Languages retrieved successfully.", languages=[LanguageOut.model_validate(language) for language in languages]
    )


@router.get(
    "/all",
    response_model=LanguageAdminListResponse,
    summary="List every language, including disabled ones, with engine settings",
    responses=errors(401, 403, 429),
)
async def list_all_languages(auth: RequireSuperAdmin, db: DbSession) -> LanguageAdminListResponse:
    languages = await LanguageService(db).list_languages(include_disabled=True)
    return LanguageAdminListResponse(
        message="Languages retrieved successfully.", languages=[LanguageAdminOut.model_validate(language) for language in languages]
    )


@router.post("", response_model=LanguageResponse, status_code=201, summary="Add a language", responses=errors(400, 401, 403, 422, 429))
async def create_language(data: LanguageCreate, auth: RequireSuperAdmin, db: DbSession) -> LanguageResponse:
    fields = data.model_dump(exclude={"code"}, exclude_none=True)
    language = await LanguageService(db).create(data.code, fields)
    return LanguageResponse(message="Language added successfully.", language=LanguageAdminOut.model_validate(language))


@router.patch("/{code}", response_model=LanguageResponse, summary="Change a language", responses=errors(401, 403, 404, 422, 429))
async def update_language(code: str, data: LanguageUpdate, auth: RequireSuperAdmin, db: DbSession) -> LanguageResponse:
    language = await LanguageService(db).update(code, data.model_dump(exclude_unset=True))
    return LanguageResponse(message="Language updated successfully.", language=LanguageAdminOut.model_validate(language))
