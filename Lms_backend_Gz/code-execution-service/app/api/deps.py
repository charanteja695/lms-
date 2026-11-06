"""FastAPI dependencies: database, request context, authentication and authorisation.

Authentication never issues or stores sessions here (see lms-backend/README.md §2-3): every request's bearer
token is verified against user-management's JWKS, then checked against the Redis access-state keys
user-management publishes so a suspended/removed user loses access within seconds, without this service
calling user-management per request.
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
from app.core.crypto import SecretCipher
from app.core.exceptions import AuthenticationError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import parse_public_id
from app.core.security import AccessTokenClaims, TokenError, get_verifier
from app.permissions.policy import can_author, can_list_own_submissions, can_practice, can_review, is_super_admin
from app.services.rate_limiter import RateLimiter

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_redis(request: Request) -> Redis:
    return cast(Redis, request.app.state.redis)


RedisDep = Annotated[Redis, Depends(get_redis)]


def get_cipher(settings: SettingsDep) -> SecretCipher:
    return SecretCipher.from_settings(settings)


CipherDep = Annotated[SecretCipher, Depends(get_cipher)]


# ------------------------------------------------------------------ path ids


def _path_id(label: str, not_found_code: str) -> Callable[[str], int]:
    def parse(value: str) -> int:
        number = parse_public_id(value)
        if number is None:
            raise NotFoundError(f"{label} not found.", code=not_found_code)
        return number

    return parse


async def run_id_path(run_id: Annotated[str, Path()]) -> int:
    return _path_id("Run", "RUN_NOT_FOUND")(run_id)


async def problem_id_path(problem_id: Annotated[str, Path()]) -> int:
    return _path_id("Problem", "PROBLEM_NOT_FOUND")(problem_id)


async def submission_id_path(submission_id: Annotated[str, Path()]) -> int:
    return _path_id("Submission", "SUBMISSION_NOT_FOUND")(submission_id)


async def test_case_id_path(test_case_id: Annotated[str, Path()]) -> int:
    return _path_id("Test case", "TEST_CASE_NOT_FOUND")(test_case_id)


RunIdParam = Annotated[int, Depends(run_id_path)]
ProblemIdParam = Annotated[int, Depends(problem_id_path)]
SubmissionIdParam = Annotated[int, Depends(submission_id_path)]
TestCaseIdParam = Annotated[int, Depends(test_case_id_path)]


# ------------------------------------------------------------------ request context


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


def rate_limit(scope: str, limit_setting: str, window_seconds: int) -> Callable[..., Awaitable[None]]:
    async def dependency(
        ctx: RequestCtx,
        settings: SettingsDep,
        limiter: RateLimiterDep,
    ) -> None:
        await limiter.hit(
            f"{scope}:ip:{ctx.ip_address or 'unknown'}",
            limit=getattr(settings, limit_setting),
            window_seconds=window_seconds,
        )

    return dependency


AuthoringRateLimit = Depends(rate_limit("code-authoring", "AUTHORING_RATE_LIMIT_PER_HOUR", 3600))

# ------------------------------------------------------------------ authentication chain

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


def require_super_admin(auth: CurrentAuth) -> AccessTokenClaims:
    if not is_super_admin(auth):
        raise PermissionDeniedError()
    return auth


def require_author(auth: CurrentAuth) -> AccessTokenClaims:
    if not can_author(auth):
        raise PermissionDeniedError()
    return auth


def require_reviewer(auth: CurrentAuth) -> AccessTokenClaims:
    if not can_review(auth):
        raise PermissionDeniedError()
    return auth


def require_practice(auth: CurrentAuth) -> AccessTokenClaims:
    if not can_practice(auth):
        raise PermissionDeniedError("You don't have access to coding practice.", code="PRACTICE_NOT_ALLOWED")
    return auth


def require_own_submissions(auth: CurrentAuth) -> AccessTokenClaims:
    if not can_list_own_submissions(auth):
        raise PermissionDeniedError()
    return auth


RequireSuperAdmin = Annotated[AccessTokenClaims, Depends(require_super_admin)]
RequirePractice = Annotated[AccessTokenClaims, Depends(require_practice)]
RequireOwnSubmissions = Annotated[AccessTokenClaims, Depends(require_own_submissions)]
RequireAuthor = Annotated[AccessTokenClaims, Depends(require_author)]
RequireReviewer = Annotated[AccessTokenClaims, Depends(require_reviewer)]


# ------------------------------------------------------------------ service callers


def require_internal_caller(
    settings: SettingsDep,
    token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None,
) -> None:
    """assessment-service calls the internal endpoints with the shared secret (there is no per-service identity
    scheme yet — same caveat as subscription-service's seat endpoints)."""
    expected = settings.INTERNAL_SERVICE_TOKEN.get_secret_value()
    if not token or not hmac.compare_digest(token.encode(), expected.encode()):
        raise PermissionDeniedError("A valid internal service token is required.", code="INTERNAL_CALLER_REQUIRED")


InternalCaller = Depends(require_internal_caller)


# ------------------------------------------------------------------ idempotency

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9_.:-]{8,80}$")


def idempotency_key(key: Annotated[str | None, Header(alias="Idempotency-Key")] = None) -> str | None:
    if key is None:
        return None
    if not _IDEMPOTENCY_KEY.fullmatch(key):
        raise ValidationFailedError(
            details=[
                {
                    "field": "Idempotency-Key",
                    "code": "INVALID_IDEMPOTENCY_KEY",
                    "message": "Use 8-80 letters, digits, dots, colons, hyphens or underscores",
                }
            ]
        )
    return key


IdempotencyKeyHeader = Annotated[str | None, Depends(idempotency_key)]
