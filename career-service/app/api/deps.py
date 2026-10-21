"""FastAPI dependencies: database, request context, authentication and authorisation.

Students use bearer tokens; institution staff and careers managers read a student's profile the same way (verified against user-management's JWKS, then checked against the Redis
access-state keys so a suspended account loses access within seconds). Other services (the tutor's hand-off) use the shared
internal token.
"""

import hmac
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated, cast

from fastapi import Depends, Header, Path, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from lms_common.access_state import TokenIdentity, is_token_revoked
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.gateway import GatewayClient
from app.core.config import Settings, get_settings
from app.core.context import RequestContext
from app.core.exceptions import AuthenticationError, NotFoundError, PermissionDeniedError
from app.core.ids import parse_public_id
from app.core.security import AccessTokenClaims, TokenError, get_verifier
from app.permissions.policy import can_manage_careers, is_student
from app.services.rate_limiter import RateLimiter

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_redis(request: Request) -> Redis:
    return cast(Redis, request.app.state.redis)


RedisDep = Annotated[Redis, Depends(get_redis)]


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
        token_version=claims.token_version, issued_at=claims.issued_at, role=claims.role,
    )
    if await is_token_revoked(request.app.state.redis, identity, key_prefix=settings.ACCESS_STATE_KEY_PREFIX):
        raise AuthenticationError("Your access has been revoked. Please log in again.", code="TOKEN_REVOKED")
    return claims


CurrentAuth = Annotated[AccessTokenClaims, Depends(_authenticate)]


# A request's method is the action it takes on the student's own profile and resumes (the matrix cells), except
# POSTs that only read (scores and checks) or that change what exists (AI suggestions for a resume, restoring a version).
_ACTION_OF = {"GET": "view", "HEAD": "view", "POST": "create", "PUT": "update", "PATCH": "update", "DELETE": "delete"}
_READS = ("/ats", "/keyword-gap", "/grammar")
_EDITS = ("/restore", "/ai/summary", "/ai/rewrite", "/ai/polish", "/ai/tailor", "/reorder")


def _action(request: Request) -> str:
    path = request.url.path
    if request.method == "POST" and path.endswith(_READS):
        return "view"
    if request.method == "POST" and path.endswith(_EDITS):
        return "update"
    return _ACTION_OF.get(request.method, "update")


def require_student(request: Request, auth: CurrentAuth) -> AccessTokenClaims:
    if not is_student(auth):
        raise PermissionDeniedError("The resume builder is for students.", code="STUDENTS_ONLY")
    if not is_student(auth, _action(request)):
        raise PermissionDeniedError("This action on your profile and resumes is turned off for your account.", code="ACTION_NOT_PERMITTED")
    return auth


def require_careers_manager(auth: CurrentAuth) -> AccessTokenClaims:
    if not can_manage_careers(auth):
        raise PermissionDeniedError()
    return auth


RequireStudent = Annotated[AccessTokenClaims, Depends(require_student)]
RequireCareersManager = Annotated[AccessTokenClaims, Depends(require_careers_manager)]


def get_gateway(settings: SettingsDep) -> GatewayClient:
    return GatewayClient(settings)


GatewayDep = Annotated[GatewayClient, Depends(get_gateway)]


def require_internal_caller(settings: SettingsDep, token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None) -> None:
    """Other backend services call ``/internal`` with the shared secret — same scheme as the other services."""
    expected = settings.INTERNAL_SERVICE_TOKEN.get_secret_value()
    if not token or not hmac.compare_digest(token.encode(), expected.encode()):
        raise PermissionDeniedError("A valid internal service token is required.", code="INTERNAL_CALLER_REQUIRED")


RequireInternalCaller = Depends(require_internal_caller)


async def _public_id_path(value: str, label: str, code: str) -> int:
    number = parse_public_id(value)
    if number is None:
        raise NotFoundError(f"{label} not found.", code=code)
    return number


async def resume_id_path(resume_id: Annotated[str, Path()]) -> int:
    return await _public_id_path(resume_id, "Resume", "RESUME_NOT_FOUND")


async def item_id_path(item_id: Annotated[str, Path()]) -> int:
    return await _public_id_path(item_id, "Profile item", "ITEM_NOT_FOUND")


async def user_id_path(user_id: Annotated[str, Path()]) -> int:
    return await _public_id_path(user_id, "Student", "STUDENT_NOT_FOUND")


ResumeIdParam = Annotated[int, Depends(resume_id_path)]
ItemIdParam = Annotated[int, Depends(item_id_path)]
UserIdParam = Annotated[int, Depends(user_id_path)]


def rate_limit_user(scope: str, limit_setting: str, window_seconds: int) -> Callable[..., Awaitable[None]]:
    async def dependency(auth: CurrentAuth, settings: SettingsDep, limiter: RateLimiterDep) -> None:
        await limiter.hit(f"{scope}:user:{auth.user_id}", limit=getattr(settings, limit_setting), window_seconds=window_seconds)

    return dependency


WriteRateLimit = Depends(rate_limit_user("career-write", "WRITE_RATE_LIMIT_PER_USER_PER_MINUTE", 60))
AiRateLimit = Depends(rate_limit_user("career-ai", "AI_RATE_LIMIT_PER_USER_PER_HOUR", 3600))
ExportRateLimit = Depends(rate_limit_user("career-export", "EXPORT_RATE_LIMIT_PER_USER_PER_HOUR", 3600))


async def public_rate_limit(request: Request, settings: SettingsDep, limiter: RateLimiterDep) -> None:
    """Public share pages are unauthenticated: limit by client address."""
    ip = request.client.host if request.client else "unknown"
    if settings.TRUST_PROXY_HEADERS and request.headers.get("x-forwarded-for"):
        ip = request.headers["x-forwarded-for"].split(",")[0].strip() or ip
    await limiter.hit(f"career-public:ip:{ip}", limit=settings.PUBLIC_RATE_LIMIT_PER_IP_PER_MINUTE, window_seconds=60)


PublicRateLimit = Depends(public_rate_limit)
