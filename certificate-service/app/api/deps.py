"""FastAPI dependencies: database, request context, authentication and authorisation.

Authentication never issues or stores sessions here (see lms-backend/README.md §2-3): every request's bearer
token is verified against user-management's JWKS, then checked against the Redis access-state keys
user-management publishes so a suspended/removed user loses access within seconds.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated, cast

from fastapi import Depends, Path, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from lms_common.access_state import TokenIdentity, is_token_revoked
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.context import RequestContext
from app.core.exceptions import AuthenticationError, NotFoundError, PermissionDeniedError
from app.core.ids import parse_public_id
from app.core.security import AccessTokenClaims, TokenError, get_verifier
from app.permissions.policy import can_author_templates, can_manage_certificates, can_publish_templates
from app.services.rate_limiter import RateLimiter

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_redis(request: Request) -> Redis:
    return cast(Redis, request.app.state.redis)


RedisDep = Annotated[Redis, Depends(get_redis)]


def _path_id(label: str, not_found_code: str) -> Callable[[str], int]:
    def parse(value: str) -> int:
        number = parse_public_id(value)
        if number is None:
            raise NotFoundError(f"{label} not found.", code=not_found_code)
        return number

    return parse


async def template_id_path(template_id: Annotated[str, Path()]) -> int:
    return _path_id("Template", "TEMPLATE_NOT_FOUND")(template_id)


async def certificate_id_path(certificate_id: Annotated[str, Path()]) -> int:
    return _path_id("Certificate", "CERTIFICATE_NOT_FOUND")(certificate_id)


TemplateIdParam = Annotated[int, Depends(template_id_path)]
CertificateIdParam = Annotated[int, Depends(certificate_id_path)]


def get_request_context(request: Request, settings: SettingsDep) -> RequestContext:
    ip_address = request.client.host if request.client else None
    if settings.TRUST_PROXY_HEADERS:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0].strip() or ip_address
    user_agent = request.headers.get("user-agent")
    return RequestContext(
        ip_address=ip_address[:45] if ip_address else None,
        user_agent=user_agent[:500] if user_agent else None,
        request_id=getattr(request.state, "request_id", None),
    )


RequestCtx = Annotated[RequestContext, Depends(get_request_context)]


def get_rate_limiter(request: Request, settings: SettingsDep) -> RateLimiter:
    return RateLimiter(request.app.state.redis, enabled=settings.RATE_LIMIT_ENABLED)


RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]

_bearer_scheme = HTTPBearer(auto_error=False, description="Access token issued by user-management's /auth/login")


async def _authenticate(
    request: Request,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> AccessTokenClaims:
    """Signature valid (JWKS) -> not revoked (Redis access-state) -> claims trusted."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Log in to continue.", code="NOT_AUTHENTICATED")
    try:
        claims = await get_verifier().verify(credentials.credentials)
    except TokenError as exc:
        raise AuthenticationError("Your access token is invalid or has expired.", code="INVALID_TOKEN") from exc

    identity = TokenIdentity(
        session_id=str(claims.session_id),
        user_id=str(claims.user_id),
        organization_id=str(claims.organization_id) if claims.organization_id else None,
        token_version=claims.token_version,
        issued_at=claims.issued_at, role=claims.role,
    )
    if await is_token_revoked(request.app.state.redis, identity, key_prefix=settings.ACCESS_STATE_KEY_PREFIX):
        raise AuthenticationError("Your access has been revoked. Please log in again.", code="TOKEN_REVOKED")
    return claims


CurrentAuth = Annotated[AccessTokenClaims, Depends(_authenticate)]


def require_template_author(auth: CurrentAuth) -> AccessTokenClaims:
    if not can_author_templates(auth):
        raise PermissionDeniedError()
    return auth


def require_template_publisher(auth: CurrentAuth) -> AccessTokenClaims:
    if not can_publish_templates(auth):
        raise PermissionDeniedError()
    return auth


def require_certificate_manager(auth: CurrentAuth) -> AccessTokenClaims:
    if not can_manage_certificates(auth):
        raise PermissionDeniedError()
    return auth


RequireTemplateAuthor = Annotated[AccessTokenClaims, Depends(require_template_author)]
RequireTemplatePublisher = Annotated[AccessTokenClaims, Depends(require_template_publisher)]
RequireCertificateManager = Annotated[AccessTokenClaims, Depends(require_certificate_manager)]


def rate_limit_user(scope: str, limit_setting: str, window_seconds: int) -> Callable[..., Awaitable[None]]:
    async def dependency(auth: CurrentAuth, settings: SettingsDep, limiter: RateLimiterDep) -> None:
        await limiter.hit(f"{scope}:user:{auth.user_id}", limit=getattr(settings, limit_setting), window_seconds=window_seconds)

    return dependency


def rate_limit_ip(scope: str, limit_setting: str, window_seconds: int) -> Callable[..., Awaitable[None]]:
    async def dependency(ctx: RequestCtx, settings: SettingsDep, limiter: RateLimiterDep) -> None:
        await limiter.hit(f"{scope}:ip:{ctx.ip_address or 'unknown'}", limit=getattr(settings, limit_setting), window_seconds=window_seconds)

    return dependency


AuthoringRateLimit = Depends(rate_limit_user("certificate-authoring", "AUTHORING_RATE_LIMIT_PER_HOUR", 3600))
DownloadRateLimit = Depends(rate_limit_user("certificate-download", "DOWNLOAD_RATE_LIMIT_PER_USER_PER_MINUTE", 60))
PublicVerifyRateLimit = Depends(rate_limit_ip("public-verify", "PUBLIC_VERIFY_RATE_LIMIT_PER_IP_PER_MINUTE", 60))
