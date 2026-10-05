"""Admin-configurable provider fallback order per capability (app/models/model_route.py), with the platform
default (app/providers/router.py::default_route) as a fallback when nothing has been configured yet."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ValidationFailedError
from app.domain.enums import Capability, ProviderName
from app.models.model_route import ModelRoute
from app.providers.router import RouteEntry, default_route, route_from_config

_VALID_PROVIDERS: dict[str, set[str]] = {Capability.CHAT.value: {ProviderName.ANTHROPIC.value}, Capability.EMBEDDING.value: {ProviderName.VOYAGE.value}}


class ModelRouteService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def resolve(self, capability: str) -> list[RouteEntry]:
        row = await self.db.get(ModelRoute, capability)
        if row is None or not row.providers:
            return default_route(self.settings, capability)
        return route_from_config(row.providers)

    async def list_all(self) -> dict[str, list[RouteEntry]]:
        return {capability: await self.resolve(capability) for capability in (Capability.CHAT, Capability.EMBEDDING)}

    async def set_route(self, capability: str, providers: list[dict[str, str]], *, updated_by: int) -> list[RouteEntry]:
        valid = _VALID_PROVIDERS.get(capability, set())
        unknown = sorted({p["provider"] for p in providers} - valid)
        if unknown:
            raise ValidationFailedError(f"Unknown provider(s) for {capability}: {', '.join(unknown)}.", code="UNKNOWN_PROVIDER")
        if not providers:
            raise ValidationFailedError("At least one provider is required.", code="EMPTY_ROUTE")
        row = await self.db.get(ModelRoute, capability)
        if row is None:
            row = ModelRoute(capability=capability)
            self.db.add(row)
        row.providers = providers
        row.updated_by = updated_by
        await self.db.commit()
        return route_from_config(providers)
