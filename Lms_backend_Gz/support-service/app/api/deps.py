"""FastAPI dependencies: database, request context, authentication and authorisation.

Students, agents and managers use bearer tokens (verified against user-management's JWKS, then checked against the Redis
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

from app.clients.tutor import TutorClient
from app.clients.user_management import UserManagementClient
from app.core.config import Settings, get_settings
from app.core.context import RequestContext
from app.core.exceptions import AuthenticationError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import parse_public_id
from app.core.security import AccessTokenClaims, TokenError, get_verifier
from app.permissions.policy import is_agent, is_manager, is_student
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


def require_student(auth: CurrentAuth) -> AccessTokenClaims:
    if not is_student(auth):
        raise PermissionDeniedError("Only students open tickets here.", code="STUDENTS_ONLY")
    return auth


def require_agent(auth: CurrentAuth) -> AccessTokenClaims:
    if not is_agent(auth):
        raise PermissionDeniedError()
    return auth


def require_manager(auth: CurrentAuth) -> AccessTokenClaims:
    if not is_manager(auth):
        raise PermissionDeniedError()
    return auth


RequireStudent = Annotated[AccessTokenClaims, Depends(require_student)]


def require_ticket_opener(auth: CurrentAuth) -> AccessTokenClaims:
    if not is_student(auth, "create"):
        raise PermissionDeniedError("Opening tickets is turned off for your account.", code="ACTION_NOT_PERMITTED")
    return auth


RequireTicketOpener = Annotated[AccessTokenClaims, Depends(require_ticket_opener)]
RequireAgent = Annotated[AccessTokenClaims, Depends(require_agent)]
RequireManager = Annotated[AccessTokenClaims, Depends(require_manager)]


def require_participant(auth: CurrentAuth) -> AccessTokenClaims:
    """Writes messages: someone who opens tickets, or answers them."""
    if not (is_student(auth) or is_agent(auth)):
        raise PermissionDeniedError()
    return auth


RequireParticipant = Annotated[AccessTokenClaims, Depends(require_participant)]


def require_internal_caller(settings: SettingsDep, token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None) -> None:
    """Other backend services call ``/internal`` with the shared secret — same scheme as the other services."""
    expected = settings.INTERNAL_SERVICE_TOKEN.get_secret_value()
    if not token or not hmac.compare_digest(token.encode(), expected.encode()):
        raise PermissionDeniedError("A valid internal service token is required.", code="INTERNAL_CALLER_REQUIRED")


RequireInternalCaller = Depends(require_internal_caller)


async def ticket_id_path(ticket_id: Annotated[str, Path()]) -> int:
    number = parse_public_id(ticket_id)
    if number is None:
        raise NotFoundError("Ticket not found.", code="TICKET_NOT_FOUND")
    return number


async def canned_id_path(canned_id: Annotated[str, Path()]) -> int:
    number = parse_public_id(canned_id)
    if number is None:
        raise NotFoundError("Canned reply not found.", code="CANNED_REPLY_NOT_FOUND")
    return number


async def message_id_path(message_id: Annotated[str, Path()]) -> int:
    number = parse_public_id(message_id)
    if number is None:
        raise NotFoundError("Message not found.", code="MESSAGE_NOT_FOUND")
    return number


TicketIdParam = Annotated[int, Depends(ticket_id_path)]
MessageIdParam = Annotated[int, Depends(message_id_path)]
CannedIdParam = Annotated[int, Depends(canned_id_path)]


def rate_limit_user(scope: str, limit_setting: str, window_seconds: int) -> Callable[..., Awaitable[None]]:
    async def dependency(auth: CurrentAuth, settings: SettingsDep, limiter: RateLimiterDep) -> None:
        await limiter.hit(f"{scope}:user:{auth.user_id}", limit=getattr(settings, limit_setting), window_seconds=window_seconds)

    return dependency


TicketRateLimit = Depends(rate_limit_user("ticket-create", "TICKET_RATE_LIMIT_PER_USER_PER_HOUR", 3600))
ReplyRateLimit = Depends(rate_limit_user("ticket-reply", "REPLY_RATE_LIMIT_PER_USER_PER_MINUTE", 60))
AttachmentRateLimit = Depends(rate_limit_user("attachment-url", "ATTACHMENT_URL_RATE_LIMIT_PER_USER_PER_MINUTE", 60))
AgentRateLimit = Depends(rate_limit_user("ticket-agent", "AGENT_RATE_LIMIT_PER_HOUR", 3600))

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9_.:-]{8,80}$")


def idempotency_key(key: Annotated[str | None, Header(alias="Idempotency-Key")] = None) -> str | None:
    if key is None:
        return None
    if not _IDEMPOTENCY_KEY.fullmatch(key):
        raise ValidationFailedError(details=[{"field": "Idempotency-Key", "code": "INVALID_IDEMPOTENCY_KEY", "message": "Use 8-80 letters, digits, dots, colons, hyphens or underscores"}])
    return key


IdempotencyKeyHeader = Annotated[str | None, Depends(idempotency_key)]


def get_tutor_client(settings: SettingsDep) -> TutorClient:
    return TutorClient(settings)


TutorClientDep = Annotated[TutorClient, Depends(get_tutor_client)]


def get_people_client(settings: SettingsDep) -> UserManagementClient:
    return UserManagementClient(settings)


PeopleClientDep = Annotated[UserManagementClient, Depends(get_people_client)]
