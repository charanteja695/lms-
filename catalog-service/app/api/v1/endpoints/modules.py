from fastapi import APIRouter

from app.api.deps import DbSession, RequireAuthor
from app.api.responses import errors
from app.api.v1.authoring_deps import DraftVersion, ModuleInVersion
from app.schemas.common import ReorderRequest
from app.schemas.module import ModuleCreate, ModuleOut, ModuleResponse, ModuleUpdate
from app.services.module_service import ModuleService

router = APIRouter(prefix="/courses/{course_id}/versions/{version_id}/modules", tags=["Modules"])


@router.post("", response_model=ModuleResponse, status_code=201, summary="Add a module", responses=errors(400, 401, 403, 404, 422))
async def create_module(version: DraftVersion, data: ModuleCreate, auth: RequireAuthor, db: DbSession) -> ModuleResponse:
    module = await ModuleService(db).create(version, data)
    return ModuleResponse(message="Module added successfully.", module=ModuleOut.model_validate(module))


@router.patch("/{module_id}", response_model=ModuleResponse, summary="Update a module", responses=errors(400, 401, 403, 404, 422))
async def update_module(module: ModuleInVersion, data: ModuleUpdate, auth: RequireAuthor, db: DbSession) -> ModuleResponse:
    module = await ModuleService(db).update(module, data)
    return ModuleResponse(message="Module updated successfully.", module=ModuleOut.model_validate(module))


@router.delete("/{module_id}", status_code=204, summary="Remove a module", responses=errors(400, 401, 403, 404))
async def delete_module(module: ModuleInVersion, auth: RequireAuthor, db: DbSession) -> None:
    await ModuleService(db).delete(module)


@router.put("/reorder", status_code=204, summary="Reorder modules", responses=errors(400, 401, 403, 404, 422))
async def reorder_modules(version: DraftVersion, data: ReorderRequest, auth: RequireAuthor, db: DbSession) -> None:
    await ModuleService(db).reorder(version, data.ordered_ids)
