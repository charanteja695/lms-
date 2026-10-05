"""The gateway's one job: decide where a request goes, refuse what must not get through, and hand it on.

Order, for every request: is the path sane -> which service owns it (never an ``internal`` path, never a service's own health/docs) -> if a bearer
token was sent, is it valid and unrevoked (a bad one is refused here; none at all is passed on, and the service decides whether it needs one) ->
rate limit (per user, else per IP; sign-in paths have their own tighter per-IP limit) -> forward.
"""

import logging

import httpx
from fastapi import APIRouter, Request
from lms_common.access_state import TokenIdentity, is_token_revoked
from redis.asyncio import Redis
from starlette.responses import Response

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, BadRequestError, NotFoundError
from app.core.security import AccessTokenClaims, TokenError, get_verifier
from app.proxy.forward import forward, safe_path
from app.proxy.routes import RouteTable
from app.services.rate_limiter import RateLimiter

logger = logging.getLogger("app.gateway")
router = APIRouter(tags=["Proxy"], include_in_schema=False)
_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"]


def client_address(request: Request, settings: Settings) -> tuple[str, str | None]:
    """(the address to treat as the caller, the X-Forwarded-For chain before it). Behind a trusted proxy the caller is the chain's first entry."""
    peer = request.client.host if request.client else "unknown"
    if settings.TRUST_PROXY_HEADERS:
        chain = request.headers.get("x-forwarded-for", "")
        first = chain.split(",")[0].strip()
        if first:
            return first[:45], chain[:500]
    return peer[:45], None


async def optional_claims(request: Request, settings: Settings, redis: Redis) -> AccessTokenClaims | None:
    header = request.headers.get("authorization")
    if header is None:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError("Log in to continue.", code="NOT_AUTHENTICATED")
    try:
        claims = await get_verifier().verify(token.strip())
    except TokenError as exc:
        raise AuthenticationError("Your access token is invalid or has expired.", code="INVALID_TOKEN") from exc
    identity = TokenIdentity(
        session_id=str(claims.session_id), user_id=str(claims.user_id), organization_id=str(claims.organization_id) if claims.organization_id else None,
        token_version=claims.token_version, issued_at=claims.issued_at,
    )
    if await is_token_revoked(redis, identity, key_prefix=settings.ACCESS_STATE_KEY_PREFIX):
        raise AuthenticationError("Your access has been revoked. Please log in again.", code="TOKEN_REVOKED")
    return claims


@router.api_route("/{path:path}", methods=_METHODS)
async def proxy(request: Request, path: str) -> Response:
    settings: Settings = request.app.state.settings
    full_path = request.scope["path"]
    if not safe_path(full_path):
        raise BadRequestError("That is not a valid path.", code="BAD_PATH")
    table: RouteTable = request.app.state.route_table
    service = table.resolve(full_path)
    base = request.app.state.upstreams.get(service) if service else None
    if service is None or base is None:
        raise NotFoundError("There is nothing at that address.", code="ROUTE_NOT_FOUND")

    redis: Redis = request.app.state.redis
    claims = await optional_claims(request, settings, redis)
    client_ip, forwarded_for = client_address(request, settings)
    limiter = RateLimiter(redis, enabled=settings.RATE_LIMIT_ENABLED)
    if full_path.startswith("/api/v1/auth/") or full_path == "/api/v1/auth":
        await limiter.hit(f"gw:auth:{client_ip}", limit=settings.RATE_LIMIT_AUTH_PER_MINUTE, window_seconds=60)
    if claims is not None:
        await limiter.hit(f"gw:user:{claims.user_id}", limit=settings.RATE_LIMIT_USER_PER_MINUTE, window_seconds=60)
    else:
        await limiter.hit(f"gw:ip:{client_ip}", limit=settings.RATE_LIMIT_ANONYMOUS_PER_MINUTE, window_seconds=60)

    http: httpx.AsyncClient = request.app.state.http
    return await forward(
        request, base_url=base, path=full_path, client=http, settings=settings, request_id=request.state.request_id, client_ip=client_ip, forwarded_for=forwarded_for
    )
