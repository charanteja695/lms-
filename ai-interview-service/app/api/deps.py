"""FastAPI dependencies: database, request context, authentication and authorisation.

Students, recruiters, employer admins, institution staff and careers managers use bearer tokens (verified against user-management's JWKS, then checked against the Redis
access-state keys so a suspended account loses access within seconds). Other services (the tutor's hand-off) use the shared
internal token.
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

from app.clients.codeexec import CodeExecutionClient
from app.clients.gateway import GatewayClient
from app.core.config import Settings, get_settings
from app.core.context import RequestContext
from app.core.exceptions import AuthenticationError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import parse_public_id
from app.core.security import AccessTokenClaims, TokenError, get_verifier
from app.permissions.policy import can_manage_careers, is_employer_member, is_student
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
        token_version=claims.token_version, issued_at=claims.issued_at,
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
RequireEmployer = Annotated[AccessTokenClaims, Depends(_require(is_employer_member, "Only a company's recruiters and admins can do this.", "EMPLOYERS_ONLY"))]
RequireEmployerOrManager = Annotated[
    AccessTokenClaims, Depends(_require(lambda a: is_employer_member(a) or can_manage_careers(a), "Only a company's team or a careers manager can do this.", "EMPLOYERS_ONLY"))
]
RequireCareersManager = Annotated[AccessTokenClaims, Depends(_require(can_manage_careers, "Only platform careers managers can do this.", "PERMISSION_DENIED"))]


def get_gateway(settings: SettingsDep) -> GatewayClient:
    return GatewayClient(settings)


def get_codeexec(settings: SettingsDep) -> CodeExecutionClient:
    return CodeExecutionClient(settings)


GatewayDep = Annotated[GatewayClient, Depends(get_gateway)]
CodeExecDep = Annotated[CodeExecutionClient, Depends(get_codeexec)]


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


async def plan_id_path(plan_id: Annotated[str, Path()]) -> int:
    return await _public_id_path(plan_id, "Interview plan", "PLAN_NOT_FOUND")


async def interview_id_path(interview_id: Annotated[str, Path()]) -> int:
    return await _public_id_path(interview_id, "Interview", "INTERVIEW_NOT_FOUND")


PlanIdParam = Annotated[int, Depends(plan_id_path)]
InterviewIdParam = Annotated[int, Depends(interview_id_path)]


def rate_limit_user(scope: str, limit_setting: str, window_seconds: int) -> Callable[..., Awaitable[None]]:
    async def dependency(auth: CurrentAuth, settings: SettingsDep, limiter: RateLimiterDep) -> None:
        await limiter.hit(f"{scope}:user:{auth.user_id}", limit=getattr(settings, limit_setting), window_seconds=window_seconds)

    return dependency


WriteRateLimit = Depends(rate_limit_user("interview-write", "WRITE_RATE_LIMIT_PER_USER_PER_MINUTE", 60))
TurnRateLimit = Depends(rate_limit_user("interview-turn", "TURN_RATE_LIMIT_PER_INTERVIEW_PER_MINUTE", 60))

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9_.:-]{8,80}$")


def idempotency_key(key: Annotated[str | None, Header(alias="Idempotency-Key")] = None) -> str | None:
    if key is None:
        return None
    if not _IDEMPOTENCY_KEY.fullmatch(key):
        raise ValidationFailedError(details=[{"field": "Idempotency-Key", "code": "INVALID_IDEMPOTENCY_KEY", "message": "Use 8-80 letters, digits, dots, colons, hyphens or underscores"}])
    return key


IdempotencyKeyHeader = Annotated[str | None, Depends(idempotency_key)]
