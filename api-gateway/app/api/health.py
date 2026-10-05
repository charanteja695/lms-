import asyncio
import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.proxy import optional_claims
from app.core.config import Settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])


@router.get("/health/live", summary="Liveness probe")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe (Redis and the route table)")
async def ready(request: Request) -> JSONResponse:
    checks: dict[str, str] = {"routes": "ok" if request.app.state.route_table.rules else "empty"}
    try:
        await request.app.state.redis.ping()
        checks["redis"] = "ok"
    except Exception:
        logger.exception("Redis readiness check failed")
        checks["redis"] = "unavailable"
    healthy = all(value == "ok" for value in checks.values())
    return JSONResponse(status_code=200 if healthy else 503, content={"status": "ok" if healthy else "degraded", "checks": checks})


@router.get("/health/upstreams", summary="Every service's liveness (super admin only)")
async def upstreams(request: Request) -> JSONResponse:
    """Asks each service's ``/health/live`` (which is never routed publicly). A super admin's bearer token is required: a list of service names is not for the public."""
    settings: Settings = request.app.state.settings
    claims = await optional_claims(request, settings, request.app.state.redis)
    if claims is None:
        raise AuthenticationError("Log in to continue.", code="NOT_AUTHENTICATED")
    if claims.role != "super_admin":
        raise PermissionDeniedError()

    async def probe(name: str, base: str) -> tuple[str, str]:
        try:
            response = await request.app.state.http.get(f"{base}/health/live", timeout=settings.HEALTH_CHECK_TIMEOUT_SECONDS)
            return name, "ok" if response.status_code == 200 else f"http {response.status_code}"
        except httpx.HTTPError:
            return name, "down"

    results = dict(await asyncio.gather(*(probe(name, base) for name, base in sorted(request.app.state.upstreams.items()))))
    return JSONResponse(status_code=200 if all(v == "ok" for v in results.values()) else 503, content={"status": "ok" if all(v == "ok" for v in results.values()) else "degraded", "services": results})
