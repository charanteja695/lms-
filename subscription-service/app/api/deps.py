"""FastAPI dependencies: database, request context, authentication and authorisation.

Authentication never issues or stores sessions here (see lms-backend/README.md §2-3): every
request's bearer token is verified against user-management's JWKS, then checked against the
Redis access-state keys user-management publishes so a suspended/removed admin loses access
within seconds, without this service calling user-management per request.
"""

import hmac
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


def get_redis(request: Request) -> Redis:
    return cast(Redis, request.app.state.redis)


RedisDep = Annotated[Redis, Depends(get_redis)]


DbSession = Annotated[AsyncSession, Depends(get_db)]


# ------------------------------------------------------------------ path ids


def _path_id(label: str, not_found_code: str) -> Callable[[str], int]:
    def parse(value: str) -> int:
        number = parse_public_id(value)
        if number is None:
            raise NotFoundError(f"{label} not found.", code=not_found_code)
        return number

    return parse


async def organization_id_path(organization_id: Annotated[str, Path()]) -> int:
    return _path_id("Institution", "INSTITUTION_NOT_FOUND")(organization_id)


async def plan_id_path(plan_id: Annotated[str, Path()]) -> int:
    return _path_id("Plan", "PLAN_NOT_FOUND")(plan_id)


async def course_request_id_path(course_request_id: Annotated[str, Path()]) -> int:
    return _path_id("Course request", "COURSE_REQUEST_NOT_FOUND")(course_request_id)


async def subscription_id_path(subscription_id: Annotated[str, Path()]) -> int:
    return _path_id("Subscription", "SUBSCRIPTION_NOT_FOUND")(subscription_id)


OrganizationIdParam = Annotated[int, Depends(organization_id_path)]
PlanIdParam = Annotated[int, Depends(plan_id_path)]
CourseRequestIdParam = Annotated[int, Depends(course_request_id_path)]
SubscriptionIdParam = Annotated[int, Depends(subscription_id_path)]


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


def require_scope(scope: Scope) -> Callable[[AccessTokenClaims], AccessTokenClaims]:
    def dependency(auth: CurrentAuth) -> AccessTokenClaims:
        if not auth.can(scope.value):
            raise PermissionDeniedError()
        return auth

    return dependency


RequireAccountsManage = Annotated[AccessTokenClaims, Depends(require_scope(Scope.ACCOUNTS_MANAGE))]


REQUEST = "subscriptions.request"  # the coarse key; heads are set per action on the Course requests page's cells


def require_institution_head(auth: CurrentAuth) -> AccessTokenClaims:
    """Submit a course request for their own institution: the ``course_requests.create`` cell (by default the head)."""
    if auth.organization_id is None or not auth.can_act("course_requests.create", REQUEST):
        raise PermissionDeniedError()
    return auth


def institutions_listed(auth: AccessTokenClaims) -> tuple[int, ...] | None:
    """Whose records a list shows: ``None`` = every institution (the super admin), an admin's own institutions, or a
    member's own institution if they may see its requests and subscriptions (``course_requests.view``)."""
    if auth.can(Scope.ACCOUNTS_MANAGE.value):
        return auth.organizations_in_care()
    if auth.organization_id is None or not auth.can_act("course_requests.view", REQUEST):
        raise PermissionDeniedError()
    return (auth.organization_id,)


def ensure_organization_visible(auth: AccessTokenClaims, organization_id: int) -> None:
    """The super admin sees every institution's records, an admin the institutions they look after, anyone else their own."""
    listed = institutions_listed(auth)
    if listed is None or organization_id in listed:
        return
    raise PermissionDeniedError()


RequireInstitutionHead = Annotated[AccessTokenClaims, Depends(require_institution_head)]


async def require_seat_caller(request: Request, settings: SettingsDep) -> None:
    """The seat endpoints are meant for service-to-service calls (learning-service reserving/
    releasing a seat on enrol/withdraw), which carry no user token — see README "Not yet
    wired". Until a platform-wide service-identity scheme exists, a shared secret in
    ``X-Internal-Service-Token`` stands in for one; a human admin acting directly still works
    via the normal accounts.manage bearer token, for support/ops use."""
    internal_token = request.headers.get("X-Internal-Service-Token")
    if internal_token and hmac.compare_digest(internal_token, settings.INTERNAL_SERVICE_TOKEN.get_secret_value()):
        return
    credentials = await _bearer_scheme(request)
    auth = await _authenticate(request, settings, credentials)
    if not auth.can(Scope.ACCOUNTS_MANAGE.value):
        raise PermissionDeniedError()


SeatCallerDep = Annotated[None, Depends(require_seat_caller)]
