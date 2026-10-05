from fastapi import APIRouter

from app.api.deps import CipherDep, CurrentAuth, DbSession, ProblemIdParam, SettingsDep
from app.api.responses import errors
from app.permissions.policy import can_review
from app.schemas.saved_code import SavedCodeOut, SavedCodeResponse, SavedCodeUpdate
from app.services.language_service import LanguageService
from app.services.problem_service import ProblemService
from app.services.run_service import check_source_sizes
from app.services.saved_code_service import SavedCodeService

router = APIRouter(prefix="/problems/{problem_id}/code", tags=["Saved code"])


@router.get(
    "/{language}",
    response_model=SavedCodeResponse,
    summary="Get my saved code for a problem in a language",
    description="Returns the starter template when nothing has been saved yet, so the editor always has something to show.",
    responses=errors(401, 404, 429),
)
async def get_saved_code(problem_id: ProblemIdParam, language: str, auth: CurrentAuth, db: DbSession, settings: SettingsDep, cipher: CipherDep) -> SavedCodeResponse:
    problem = await ProblemService(db, settings, cipher).get_visible(problem_id, is_reviewer=can_review(auth))
    lang = await LanguageService(db).get(language)
    saved = await SavedCodeService(db).get(auth.user_id, problem, lang)
    return SavedCodeResponse(
        message="Saved code retrieved successfully.",
        saved_code=SavedCodeOut(
            problem_id=problem.public_id,
            language=lang.code,
            source=saved.source if saved else lang.starter_template,
            updated_at=saved.updated_at if saved else None,
        ),
    )


@router.put("/{language}", response_model=SavedCodeResponse, summary="Save my code for a problem in a language", responses=errors(401, 404, 422, 429))
async def save_code(problem_id: ProblemIdParam, language: str, data: SavedCodeUpdate, auth: CurrentAuth, db: DbSession, settings: SettingsDep, cipher: CipherDep) -> SavedCodeResponse:
    problem = await ProblemService(db, settings, cipher).get_visible(problem_id, is_reviewer=can_review(auth))
    lang = await LanguageService(db).get(language)
    check_source_sizes(settings, data.source, allow_empty=True)  # an empty draft is fine; only the size matters
    saved = await SavedCodeService(db).save(auth.user_id, problem, lang, data.source)
    return SavedCodeResponse(
        message="Code saved successfully.",
        saved_code=SavedCodeOut(problem_id=problem.public_id, language=lang.code, source=saved.source, updated_at=saved.updated_at),
    )
