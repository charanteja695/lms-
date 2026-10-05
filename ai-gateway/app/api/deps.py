"""FastAPI dependencies: database, request context, authentication and authorisation.

Two callers, two schemes. People manage the prompt registry, quotas and model routing through the admin API,
authenticated the usual way (a bearer token verified against user-management's JWKS, then checked against the
Redis access-state keys). Other services call the completion/embedding/speech API on behalf of an org and user
they already authenticated themselves, with the shared internal service token instead — see
app/permissions/policy.py's docstring for why there is no per-person policy on that half of the API.
"""

import hmac
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated, cast

from fastapi import Depends, Header, Path, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from lms_common.access_state import TokenIdentity, is_token_revoked
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.context import RequestContext
from app.core.exceptions import AuthenticationError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import parse_public_id
from app.core.security import AccessTokenClaims, TokenError, get_verifier
from app.permissions.policy import can_manage_ai, can_view_org_usage
from app.providers.registry import ProviderRegistry, get_registry
from app.services.rate_limiter import RateLimiter

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_redis(request: Request) -> Redis:
    return cast(Redis, request.app.state.redis)


RedisDep = Annotated[Redis, Depends(get_redis)]


def get_provider_registry(settings: SettingsDep) -> ProviderRegistry:
    return get_registry(settings)


ProviderRegistryDep = Annotated[ProviderRegistry, Depends(get_provider_registry)]


def get_request_context(request: Request, settings: SettingsDep) -> RequestContext:
    ip_address = request.client.host if request.client else None
    if settings.TRUST_PROXY_HEADERS:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0].strip() or ip_address
    user_agent = request.headers.get("user-agent")
    return RequestContext(ip_address=ip_address[:45] if ip_address else None, user_agent=user_agent[:500] if user_agent else None, request_id=getattr(request.state, "request_id", None))


RequestCtx = Annotated[RequestContext, Depends(get_request_context)]


def get_rate_limiter(request: Request, settings: SettingsDep) -> RateLimiter:
    return RateLimiter(request.app.state.redis, enabled=settings.RATE_LIMIT_ENABLED)


RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]

_bearer_scheme = HTTPBearer(auto_error=False, description="Access token issued by user-management's /auth/login")


async def _authenticate(request: Request, settings: SettingsDep, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)]) -> AccessTokenClaims:
    """Signature valid (JWKS) -> not revoked (Redis access-state) -> claims trusted."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Log in to continue.", code="NOT_AUTHENTICATED")
    try:
        claims = await get_verifier().verify(credentials.credentials)
    except TokenError as exc:
        raise AuthenticationError("Your access token is invalid or has expired.", code="INVALID_TOKEN") from exc

    identity = TokenIdentity(
        session_id=str(claims.session_id), user_id=str(claims.user_id),
        organization_id=str(claims.organization_id) if claims.organization_id else None,
        token_version=claims.token_version, issued_at=claims.issued_at,
    )
    if await is_token_revoked(request.app.state.redis, identity, key_prefix=settings.ACCESS_STATE_KEY_PREFIX):
        raise AuthenticationError("Your access has been revoked. Please log in again.", code="TOKEN_REVOKED")
    return claims


CurrentAuth = Annotated[AccessTokenClaims, Depends(_authenticate)]


def require_ai_manager(auth: CurrentAuth) -> AccessTokenClaims:
    if not can_manage_ai(auth):
        raise PermissionDeniedError()
    return auth


RequireAiManager = Annotated[AccessTokenClaims, Depends(require_ai_manager)]
# For router-level `dependencies=[...]` lists, which need a bare Depends(), not the Annotated alias above.
RequireAiManagerDep = Depends(require_ai_manager)


def require_internal_caller(settings: SettingsDep, token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None) -> None:
    """Other backend services (ai-tutor-service, support-service, career-service, job-portal-service,
    ai-interview-service) call the completion/embedding/speech API with the shared secret — same scheme as
    subscription-service's seat endpoints and assessment-service's internal API; no per-service identity yet."""
    expected = settings.INTERNAL_SERVICE_TOKEN.get_secret_value()
    if not token or not hmac.compare_digest(token.encode(), expected.encode()):
        raise PermissionDeniedError("A valid internal service token is required.", code="INTERNAL_CALLER_REQUIRED")


RequireInternalCaller = Depends(require_internal_caller)


async def organization_id_path(organization_id: Annotated[str, Path()]) -> int:
    number = parse_public_id(organization_id)
    if number is None:
        raise NotFoundError("Organization not found.", code="ORGANIZATION_NOT_FOUND")
    return number


OrganizationIdParam = Annotated[int, Depends(organization_id_path)]


def require_view_org_usage(organization_id: OrganizationIdParam, auth: CurrentAuth) -> AccessTokenClaims:
    if not can_view_org_usage(auth, organization_id=organization_id):
        raise PermissionDeniedError()
    return auth


RequireViewOrgUsage = Annotated[AccessTokenClaims, Depends(require_view_org_usage)]


def rate_limit_user(scope: str, limit_setting: str, window_seconds: int) -> Callable[..., Awaitable[None]]:
    async def dependency(auth: CurrentAuth, settings: SettingsDep, limiter: RateLimiterDep) -> None:
        await limiter.hit(f"{scope}:user:{auth.user_id}", limit=getattr(settings, limit_setting), window_seconds=window_seconds)

    return dependency


AdminRateLimit = Depends(rate_limit_user("ai-admin", "ADMIN_RATE_LIMIT_PER_HOUR", 3600))

# ------------------------------------------------------------------ idempotency

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9_.:-]{8,80}$")


def idempotency_key(key: Annotated[str | None, Header(alias="Idempotency-Key")] = None) -> str | None:
    if key is None:
        return None
    if not _IDEMPOTENCY_KEY.fullmatch(key):
        raise ValidationFailedError(details=[{"field": "Idempotency-Key", "code": "INVALID_IDEMPOTENCY_KEY", "message": "Use 8-80 letters, digits, dots, colons, hyphens or underscores"}])
    return key


IdempotencyKeyHeader = Annotated[str | None, Depends(idempotency_key)]
