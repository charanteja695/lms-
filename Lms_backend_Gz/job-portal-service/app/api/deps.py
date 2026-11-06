"""FastAPI dependencies: database, request context, authentication and authorisation.

Students, recruiters, employer admins, institution staff and careers managers use bearer tokens (verified against user-management's JWKS, then checked against the Redis
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

from app.clients.career import CareerClient
from app.clients.gateway import GatewayClient
from app.core.config import Settings, get_settings
from app.core.context import RequestContext
from app.core.exceptions import AuthenticationError, NotFoundError, PermissionDeniedError
from app.core.ids import parse_public_id
from app.core.security import AccessTokenClaims, TokenError, get_verifier
from app.permissions.policy import (
    can_manage_careers,
    is_employer_admin,
    is_employer_member,
    is_institution_head,
    is_institution_staff,
    is_student,
)
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


def _require(check: Callable[[AccessTokenClaims], bool], message: str, code: str) -> Callable[[CurrentAuth], AccessTokenClaims]:
    def dependency(auth: CurrentAuth) -> AccessTokenClaims:
        if not check(auth):
            raise PermissionDeniedError(message, code=code)
        return auth

    return dependency


RequireStudent = Annotated[AccessTokenClaims, Depends(_require(is_student, "Only students can do this.", "STUDENTS_ONLY"))]
RequireApplicant = Annotated[AccessTokenClaims, Depends(_require(lambda a: is_student(a, "create"), "Applying is turned off for your account.", "ACTION_NOT_PERMITTED"))]
RequireWithdrawer = Annotated[AccessTokenClaims, Depends(_require(lambda a: is_student(a, "revoke"), "Withdrawing is turned off for your account.", "ACTION_NOT_PERMITTED"))]
RequireEmployer = Annotated[AccessTokenClaims, Depends(_require(is_employer_member, "Only a company's recruiters and admins can do this.", "EMPLOYERS_ONLY"))]
RequireEmployerOrManager = Annotated[
    AccessTokenClaims, Depends(_require(lambda a: is_employer_member(a) or can_manage_careers(a), "Only a company's team or a careers manager can do this.", "EMPLOYERS_ONLY"))
]
RequireEmployerAdmin = Annotated[AccessTokenClaims, Depends(_require(is_employer_admin, "Only a company's admin can do this.", "EMPLOYER_ADMIN_ONLY"))]
RequireCareersManager = Annotated[AccessTokenClaims, Depends(_require(can_manage_careers, "Only platform careers managers can do this.", "PERMISSION_DENIED"))]
RequireInstitutionMember = Annotated[AccessTokenClaims, Depends(_require(is_institution_staff, "Only institution staff can do this.", "INSTITUTION_ONLY"))]
RequireInstitutionHead = Annotated[AccessTokenClaims, Depends(_require(is_institution_head, "Only an institution head can do this.", "INSTITUTION_HEAD_ONLY"))]


def get_gateway(settings: SettingsDep) -> GatewayClient:
    return GatewayClient(settings)


GatewayDep = Annotated[GatewayClient, Depends(get_gateway)]


def get_career(settings: SettingsDep) -> CareerClient:
    return CareerClient(settings)


CareerDep = Annotated[CareerClient, Depends(get_career)]


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


async def job_id_path(job_id: Annotated[str, Path()]) -> int:
    return await _public_id_path(job_id, "Job", "JOB_NOT_FOUND")


async def application_id_path(application_id: Annotated[str, Path()]) -> int:
    return await _public_id_path(application_id, "Application", "APPLICATION_NOT_FOUND")


async def drive_id_path(drive_id: Annotated[str, Path()]) -> int:
    return await _public_id_path(drive_id, "Placement drive", "DRIVE_NOT_FOUND")


async def org_id_path(organization_id: Annotated[str, Path()]) -> int:
    return await _public_id_path(organization_id, "Organisation", "ORGANIZATION_NOT_FOUND")


JobIdParam = Annotated[int, Depends(job_id_path)]
ApplicationIdParam = Annotated[int, Depends(application_id_path)]
DriveIdParam = Annotated[int, Depends(drive_id_path)]
OrgIdParam = Annotated[int, Depends(org_id_path)]


def rate_limit_user(scope: str, limit_setting: str, window_seconds: int) -> Callable[..., Awaitable[None]]:
    async def dependency(auth: CurrentAuth, settings: SettingsDep, limiter: RateLimiterDep) -> None:
        await limiter.hit(f"{scope}:user:{auth.user_id}", limit=getattr(settings, limit_setting), window_seconds=window_seconds)

    return dependency


WriteRateLimit = Depends(rate_limit_user("jobs-write", "WRITE_RATE_LIMIT_PER_USER_PER_MINUTE", 60))
ApplyRateLimit = Depends(rate_limit_user("jobs-apply", "APPLY_RATE_LIMIT_PER_USER_PER_HOUR", 3600))
AiRateLimit = Depends(rate_limit_user("jobs-ai", "AI_RATE_LIMIT_PER_USER_PER_HOUR", 3600))
