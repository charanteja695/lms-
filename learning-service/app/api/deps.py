"""FastAPI dependencies: database, request context, authentication and authorisation.

Authentication never issues or stores sessions here (see lms-backend/README.md §2-3): every
request's bearer token is verified against user-management's JWKS, then checked against the
Redis access-state keys user-management publishes so a suspended/removed admin loses access
within seconds, without this service calling user-management per request.
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
from app.permissions.scopes import Scope
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


async def batch_id_path(batch_id: Annotated[str, Path()]) -> int:
    return _path_id("Batch", "BATCH_NOT_FOUND")(batch_id)


async def enrollment_id_path(enrollment_id: Annotated[str, Path()]) -> int:
    return _path_id("Enrollment", "ENROLLMENT_NOT_FOUND")(enrollment_id)


async def topic_item_id_path(topic_item_id: Annotated[str, Path()]) -> int:
    return _path_id("Topic item", "TOPIC_ITEM_NOT_FOUND")(topic_item_id)


BatchIdParam = Annotated[int, Depends(batch_id_path)]
EnrollmentIdParam = Annotated[int, Depends(enrollment_id_path)]
TopicItemIdParam = Annotated[int, Depends(topic_item_id_path)]


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


def rate_limit(scope: str, limit_setting: str, window_seconds: int) -> Callable[..., Awaitable[None]]:
    async def dependency(
        ctx: RequestCtx,
        settings: SettingsDep,
        limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    ) -> None:
        await limiter.hit(
            f"{scope}:ip:{ctx.ip_address or 'unknown'}",
            limit=getattr(settings, limit_setting),
            window_seconds=window_seconds,
        )

    return dependency


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


# Permissions come from the access token (user-management's catalog; a super admin can grant or remove any per person):
#   learning.study          their own enrolments and progress (a student)
#   learning.batches.view   their own institution's batches and who is in them (staff, head)
#   learning.batches.manage create batches, enrol and withdraw, for their own institution (a head)
#   accounts.manage         every institution's batches and enrolments
STUDY, BATCHES_VIEW, BATCHES_MANAGE = "learning.study", "learning.batches.view", "learning.batches.manage"


def sees_all_institutions(auth: AccessTokenClaims) -> bool:
    """accounts.manage: the super admin reaches every institution, an admin only the ones they look after."""
    return auth.can(Scope.ACCOUNTS_MANAGE.value)


def institutions_in_care(auth: AccessTokenClaims) -> tuple[int, ...] | None:
    """For accounts.manage: ``None`` = every institution (the super admin), else the admin's own institutions."""
    return auth.organizations_in_care()


def manages_institution(auth: AccessTokenClaims, organization_id: int) -> bool:
    care = institutions_in_care(auth)
    return sees_all_institutions(auth) and (care is None or organization_id in care)


def sees_own_batches(auth: AccessTokenClaims) -> bool:
    return auth.organization_id is not None and (auth.has_scope(BATCHES_VIEW) or auth.has_scope(BATCHES_MANAGE))


def require_scope(scope: Scope) -> Callable[[AccessTokenClaims], AccessTokenClaims]:
    def dependency(auth: CurrentAuth) -> AccessTokenClaims:
        if not auth.can(scope.value):
            raise PermissionDeniedError()
        return auth

    return dependency


RequireAccountsManage = Annotated[AccessTokenClaims, Depends(require_scope(Scope.ACCOUNTS_MANAGE))]


def require_batch_manager(auth: CurrentAuth) -> AccessTokenClaims:
    """Creates/manages batches and enrolments: an institution head for their own institution,
    or a platform admin for any institution."""
    if sees_all_institutions(auth):
        return auth
    if auth.organization_id is not None and auth.has_scope(BATCHES_MANAGE):
        return auth
    raise PermissionDeniedError()


RequireBatchManager = Annotated[AccessTokenClaims, Depends(require_batch_manager)]


def ensure_organization_visible(auth: AccessTokenClaims, organization_id: int) -> None:
    """accounts.manage sees every institution's records; anyone else only their own."""
    if manages_institution(auth, organization_id) or (auth.organization_id == organization_id and sees_own_batches(auth)):
        return
    raise PermissionDeniedError()
