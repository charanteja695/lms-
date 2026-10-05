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
from app.core.exceptions import AuthenticationError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import parse_public_id
from app.core.security import AccessTokenClaims, TokenError, get_verifier
from app.permissions.policy import can_author, can_manage_exams, is_student, is_super_admin
from app.services.rate_limiter import RateLimiter

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_redis(request: Request) -> Redis:
    return cast(Redis, request.app.state.redis)


RedisDep = Annotated[Redis, Depends(get_redis)]


# ------------------------------------------------------------------ path ids


def _path_id(label: str, not_found_code: str) -> Callable[[str], int]:
    def parse(value: str) -> int:
        number = parse_public_id(value)
        if number is None:
            raise NotFoundError(f"{label} not found.", code=not_found_code)
        return number

    return parse


async def question_id_path(question_id: Annotated[str, Path()]) -> int:
    return _path_id("Question", "QUESTION_NOT_FOUND")(question_id)


async def test_id_path(test_id: Annotated[str, Path()]) -> int:
    return _path_id("Test", "TEST_NOT_FOUND")(test_id)


async def attempt_id_path(attempt_id: Annotated[str, Path()]) -> int:
    return _path_id("Attempt", "ATTEMPT_NOT_FOUND")(attempt_id)


async def schedule_id_path(schedule_id: Annotated[str, Path()]) -> int:
    return _path_id("Schedule", "SCHEDULE_NOT_FOUND")(schedule_id)


QuestionIdParam = Annotated[int, Depends(question_id_path)]
TestIdParam = Annotated[int, Depends(test_id_path)]
AttemptIdParam = Annotated[int, Depends(attempt_id_path)]
ScheduleIdParam = Annotated[int, Depends(schedule_id_path)]


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
        issued_at=claims.issued_at,
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


def require_exam_manager(auth: CurrentAuth) -> AccessTokenClaims:
    if not can_manage_exams(auth):
        raise PermissionDeniedError()
    return auth


def require_student(auth: CurrentAuth) -> AccessTokenClaims:
    """Takes tests. Staff, heads and admins review and manage, they do not sit papers."""
    if not is_student(auth):
        raise PermissionDeniedError("Only students take tests.", code="STUDENTS_ONLY")
    return auth


RequireSuperAdmin = Annotated[AccessTokenClaims, Depends(require_super_admin)]
RequireAuthor = Annotated[AccessTokenClaims, Depends(require_author)]
RequireExamManager = Annotated[AccessTokenClaims, Depends(require_exam_manager)]
RequireStudent = Annotated[AccessTokenClaims, Depends(require_student)]


def rate_limit_user(scope: str, limit_setting: str, window_seconds: int) -> Callable[..., Awaitable[None]]:
    """Per signed-in user (a shared campus IP must not throttle a whole class)."""

    async def dependency(auth: CurrentAuth, settings: SettingsDep, limiter: RateLimiterDep) -> None:
        await limiter.hit(
            f"{scope}:user:{auth.user_id}", limit=getattr(settings, limit_setting), window_seconds=window_seconds
        )

    return dependency


AuthoringRateLimit = Depends(rate_limit_user("assessment-authoring", "AUTHORING_RATE_LIMIT_PER_HOUR", 3600))
AnswerSaveRateLimit = Depends(rate_limit_user("answer-save", "ANSWER_SAVE_RATE_LIMIT_PER_USER_PER_MINUTE", 60))
AttemptCreateRateLimit = Depends(rate_limit_user("attempt-create", "ATTEMPT_CREATE_RATE_LIMIT_PER_USER_PER_MINUTE", 60))
FileUrlRateLimit = Depends(rate_limit_user("file-url", "FILE_URL_RATE_LIMIT_PER_USER_PER_MINUTE", 60))


# ------------------------------------------------------------------ service callers


def require_internal_caller(
    settings: SettingsDep,
    token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None,
) -> None:
    """proctoring-service and job-portal-service call the internal endpoints with the shared secret (there is no
    per-service identity scheme yet — same caveat as subscription-service's seat endpoints)."""
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
