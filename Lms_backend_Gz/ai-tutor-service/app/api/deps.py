"""FastAPI dependencies: database, request context, authentication and authorisation.

Students use the tutor with a bearer token (verified against user-management's JWKS, then checked against the Redis
access-state keys so a suspended account loses access within seconds). Authors, institution staff and support managers use
the admin endpoints the same way. support-service reads a conversation's transcript with the shared internal token instead.
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

from app.clients.gateway import GatewayClient
from app.clients.support import SupportClient
from app.core.config import Settings, get_settings
from app.core.context import RequestContext
from app.core.exceptions import AuthenticationError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import parse_public_id
from app.core.security import AccessTokenClaims, TokenError, get_verifier
from app.permissions.policy import can_author, can_manage_index, can_manage_support, is_student
from app.rag.index_cache import IndexCache
from app.services.rate_limiter import RateLimiter

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_redis(request: Request) -> Redis:
    return cast(Redis, request.app.state.redis)


RedisDep = Annotated[Redis, Depends(get_redis)]


def get_gateway(settings: SettingsDep) -> GatewayClient:
    return GatewayClient(settings)


GatewayDep = Annotated[GatewayClient, Depends(get_gateway)]


def get_support_client(settings: SettingsDep) -> SupportClient:
    return SupportClient(settings)


SupportDep = Annotated[SupportClient, Depends(get_support_client)]


def get_index_cache(request: Request) -> IndexCache:
    return cast(IndexCache, request.app.state.index_cache)


IndexCacheDep = Annotated[IndexCache, Depends(get_index_cache)]


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
        raise PermissionDeniedError("The tutor is for students.", code="STUDENTS_ONLY")
    return auth


def require_support_manager(auth: CurrentAuth) -> AccessTokenClaims:
    if not can_manage_support(auth):
        raise PermissionDeniedError()
    return auth


def require_author(auth: CurrentAuth) -> AccessTokenClaims:
    if not (can_author(auth) or can_manage_support(auth)):
        raise PermissionDeniedError()
    return auth


def require_index_manager(auth: CurrentAuth) -> AccessTokenClaims:
    if not can_manage_index(auth):
        raise PermissionDeniedError()
    return auth


RequireStudent = Annotated[AccessTokenClaims, Depends(require_student)]
RequireSupportManager = Annotated[AccessTokenClaims, Depends(require_support_manager)]
def require_index_reader(auth: CurrentAuth) -> AccessTokenClaims:
    """Index status: the authors who own the content, and the AI managers who reindex it (they need the version ids)."""
    if not (can_author(auth) or can_manage_support(auth) or can_manage_index(auth)):
        raise PermissionDeniedError()
    return auth


RequireAuthor = Annotated[AccessTokenClaims, Depends(require_author)]
RequireIndexManager = Annotated[AccessTokenClaims, Depends(require_index_manager)]
RequireIndexReader = Annotated[AccessTokenClaims, Depends(require_index_reader)]


def require_internal_caller(settings: SettingsDep, token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None) -> None:
    """Other backend services (ai-tutor-service, support-service, career-service, job-portal-service,
    ai-interview-service) call the completion/embedding/speech API with the shared secret — same scheme as
    subscription-service's seat endpoints and assessment-service's internal API; no per-service identity yet."""
    expected = settings.INTERNAL_SERVICE_TOKEN.get_secret_value()
    if not token or not hmac.compare_digest(token.encode(), expected.encode()):
        raise PermissionDeniedError("A valid internal service token is required.", code="INTERNAL_CALLER_REQUIRED")


RequireInternalCaller = Depends(require_internal_caller)


async def _public_id_path(value: str, label: str, code: str) -> int:
    number = parse_public_id(value)
    if number is None:
        raise NotFoundError(f"{label} not found.", code=code)
    return number


async def conversation_id_path(conversation_id: Annotated[str, Path()]) -> int:
    return await _public_id_path(conversation_id, "Conversation", "CONVERSATION_NOT_FOUND")


async def message_id_path(message_id: Annotated[str, Path()]) -> int:
    return await _public_id_path(message_id, "Message", "MESSAGE_NOT_FOUND")


async def faq_id_path(faq_id: Annotated[str, Path()]) -> int:
    return await _public_id_path(faq_id, "FAQ entry", "FAQ_NOT_FOUND")


async def escalation_id_path(escalation_id: Annotated[str, Path()]) -> int:
    return await _public_id_path(escalation_id, "Escalation", "ESCALATION_NOT_FOUND")


async def eval_set_id_path(eval_set_id: Annotated[str, Path()]) -> int:
    return await _public_id_path(eval_set_id, "Evaluation set", "EVAL_SET_NOT_FOUND")


async def eval_run_id_path(run_id: Annotated[str, Path()]) -> int:
    return await _public_id_path(run_id, "Evaluation run", "EVAL_RUN_NOT_FOUND")


ConversationIdParam = Annotated[int, Depends(conversation_id_path)]
MessageIdParam = Annotated[int, Depends(message_id_path)]
FaqIdParam = Annotated[int, Depends(faq_id_path)]
EscalationIdParam = Annotated[int, Depends(escalation_id_path)]
EvalSetIdParam = Annotated[int, Depends(eval_set_id_path)]
EvalRunIdParam = Annotated[int, Depends(eval_run_id_path)]


def rate_limit_user(scope: str, limit_setting: str, window_seconds: int) -> Callable[..., Awaitable[None]]:
    async def dependency(auth: CurrentAuth, settings: SettingsDep, limiter: RateLimiterDep) -> None:
        await limiter.hit(f"{scope}:user:{auth.user_id}", limit=getattr(settings, limit_setting), window_seconds=window_seconds)

    return dependency


AuthoringRateLimit = Depends(rate_limit_user("tutor-authoring", "AUTHORING_RATE_LIMIT_PER_HOUR", 3600))
MessageRateLimit = Depends(rate_limit_user("tutor-message", "MESSAGE_RATE_LIMIT_PER_USER_PER_MINUTE", 60))
ConversationRateLimit = Depends(rate_limit_user("tutor-conversation", "CONVERSATION_RATE_LIMIT_PER_USER_PER_HOUR", 3600))

# ------------------------------------------------------------------ idempotency

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9_.:-]{8,80}$")


def idempotency_key(key: Annotated[str | None, Header(alias="Idempotency-Key")] = None) -> str | None:
    if key is None:
        return None
    if not _IDEMPOTENCY_KEY.fullmatch(key):
        raise ValidationFailedError(details=[{"field": "Idempotency-Key", "code": "INVALID_IDEMPOTENCY_KEY", "message": "Use 8-80 letters, digits, dots, colons, hyphens or underscores"}])
    return key


IdempotencyKeyHeader = Annotated[str | None, Depends(idempotency_key)]
