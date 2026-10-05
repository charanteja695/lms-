"""The prompt registry's admin API (`ai.manage`) — docs/PRODUCT.md §6: "prompt registry + versions"."""

from typing import Annotated

from fastapi import APIRouter, Path, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import AdminRateLimit, DbSession, RequireAiManager, RequireAiManagerDep
from app.api.responses import errors
from app.schemas.prompt import (
    PromptCreateIn,
    PromptListResponse,
    PromptOut,
    PromptResponse,
    PromptVersionCreateIn,
    PromptVersionOut,
    PromptVersionResponse,
)
from app.services.prompt_service import PromptService

router = APIRouter(prefix="/prompts", tags=["Prompts"], dependencies=[RequireAiManagerDep, AdminRateLimit])


@router.post("", response_model=PromptResponse, status_code=201, summary="Register a new prompt", responses=errors(401, 403, 409, 422, 429))
async def create_prompt(body: PromptCreateIn, db: DbSession, auth: RequireAiManager) -> PromptResponse:
    prompt = await PromptService(db).create_prompt(key=body.key, capability=body.capability, owner_service=body.owner_service, description=body.description, created_by=auth.user_id)
    return PromptResponse(message="Prompt created.", prompt=PromptOut.model_validate(prompt))


@router.get("", response_model=PromptListResponse, summary="List prompts", responses=errors(401, 403, 429))
async def list_prompts(db: DbSession, page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 20) -> PromptListResponse:
    prompts, total, is_exact = await PromptService(db).list_prompts(page=page, per_page=per_page)
    context = PageContext.build(page=page, per_page=per_page, total=total, is_exact=is_exact, sort_column="created_at", sort_order=SortOrder.DESC)
    return PromptListResponse(message="", prompts=[PromptOut.model_validate(p) for p in prompts], page_context=context)


@router.get("/{key}", response_model=PromptResponse, summary="Get a prompt", responses=errors(401, 403, 404, 429))
async def get_prompt(key: Annotated[str, Path()], db: DbSession) -> PromptResponse:
    prompt = await PromptService(db).get_prompt(key)
    return PromptResponse(message="", prompt=PromptOut.model_validate(prompt))


@router.post("/{key}/versions", response_model=PromptVersionResponse, status_code=201, summary="Draft a new version", responses=errors(401, 403, 404, 422, 429))
async def create_version(key: Annotated[str, Path()], body: PromptVersionCreateIn, db: DbSession, auth: RequireAiManager) -> PromptVersionResponse:
    service = PromptService(db)
    prompt = await service.get_prompt(key)
    version = await service.create_version(prompt, template=body.template, variables=body.variables, allowed_tools=body.allowed_tools, model_params=body.model_params, created_by=auth.user_id)
    return PromptVersionResponse(message="Prompt version created.", version=PromptVersionOut.model_validate(version))


@router.post("/{key}/versions/{version}/activate", response_model=PromptVersionResponse, summary="Activate a draft version", description="Must be activated by someone other than its author (see app/services/prompt_service.py).", responses=errors(401, 403, 404, 409, 429))
async def activate_version(key: Annotated[str, Path()], version: Annotated[int, Path(ge=1)], db: DbSession, auth: RequireAiManager) -> PromptVersionResponse:
    service = PromptService(db)
    prompt = await service.get_prompt(key)
    row = await service.get_version(prompt, version)
    activated = await service.activate_version(prompt, row, activated_by=auth.user_id)
    return PromptVersionResponse(message="Prompt version activated.", version=PromptVersionOut.model_validate(activated))


@router.post("/{key}/versions/{version}/retire", response_model=PromptVersionResponse, summary="Retire a version", responses=errors(401, 403, 404, 429))
async def retire_version(key: Annotated[str, Path()], version: Annotated[int, Path(ge=1)], db: DbSession, auth: RequireAiManager) -> PromptVersionResponse:
    service = PromptService(db)
    prompt = await service.get_prompt(key)
    row = await service.get_version(prompt, version)
    retired = await service.retire_version(row, retired_by=auth.user_id)
    return PromptVersionResponse(message="Prompt version retired.", version=PromptVersionOut.model_validate(retired))
