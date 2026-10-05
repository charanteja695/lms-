"""Provider/model routing admin API (docs/PRODUCT.md §6: "provider routing"). See app/providers/router.py."""

from typing import Annotated

from fastapi import APIRouter, Path

from app.api.deps import AdminRateLimit, DbSession, RequireAiManager, RequireAiManagerDep, SettingsDep
from app.api.responses import errors
from app.domain.enums import Capability
from app.schemas.model_route import (
    ModelRouteResponse,
    ModelRouteSetIn,
    ModelRoutesOut,
    ModelRoutesResponse,
    RouteEntryOut,
)
from app.services.model_route_service import ModelRouteService

router = APIRouter(prefix="/models", tags=["Models"], dependencies=[RequireAiManagerDep, AdminRateLimit])


@router.get("", response_model=ModelRoutesResponse, summary="See the current provider routing", responses=errors(401, 403, 429))
async def get_routes(db: DbSession, settings: SettingsDep) -> ModelRoutesResponse:
    routes = await ModelRouteService(db, settings).list_all()
    out = ModelRoutesOut(
        chat=[RouteEntryOut(provider=e.provider, model=e.model) for e in routes[Capability.CHAT]],
        embedding=[RouteEntryOut(provider=e.provider, model=e.model) for e in routes[Capability.EMBEDDING]],
    )
    return ModelRoutesResponse(message="", models=out)


@router.patch("/{capability}", response_model=ModelRouteResponse, summary="Set a capability's provider fallback order", responses=errors(401, 403, 422, 429))
async def set_route(capability: Annotated[Capability, Path()], body: ModelRouteSetIn, db: DbSession, settings: SettingsDep, auth: RequireAiManager) -> ModelRouteResponse:
    entries = await ModelRouteService(db, settings).set_route(capability.value, [{"provider": e.provider, "model": e.model} for e in body.providers], updated_by=auth.user_id)
    return ModelRouteResponse(message="Routing updated.", capability=capability, providers=[RouteEntryOut(provider=e.provider, model=e.model) for e in entries])
