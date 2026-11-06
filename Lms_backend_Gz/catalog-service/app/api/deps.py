"""FastAPI dependencies: database, request context, authentication and authorisation.

Authentication never issues or stores sessions here (see lms-backend/README.md §2-3): every
request's bearer token is verified against user-management's JWKS, then checked against the
Redis access-state keys user-management publishes so a suspended/removed admin loses access
within seconds, without this service calling user-management per request.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Path, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from lms_common.access_state import TokenIdentity, is_token_revoked
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


# ------------------------------------------------------------------ path ids


def _path_id(label: str, not_found_code: str) -> Callable[[str], int]:
    def parse(value: str) -> int:
        number = parse_public_id(value)
        if number is None:
            # A malformed id can never exist, so it is reported exactly like an unknown id.
            raise NotFoundError(f"{label} not found.", code=not_found_code)
        return number

    return parse


async def course_id_path(course_id: Annotated[str, Path()]) -> int:
    return _path_id("Course", "COURSE_NOT_FOUND")(course_id)


async def version_id_path(version_id: Annotated[str, Path()]) -> int:
    return _path_id("Course version", "COURSE_VERSION_NOT_FOUND")(version_id)


async def module_id_path(module_id: Annotated[str, Path()]) -> int:
    return _path_id("Module", "MODULE_NOT_FOUND")(module_id)


async def topic_id_path(topic_id: Annotated[str, Path()]) -> int:
    return _path_id("Topic", "TOPIC_NOT_FOUND")(topic_id)


async def topic_item_id_path(topic_item_id: Annotated[str, Path()]) -> int:
    return _path_id("Topic item", "TOPIC_ITEM_NOT_FOUND")(topic_item_id)


async def learning_path_id_path(learning_path_id: Annotated[str, Path()]) -> int:
    return _path_id("Learning path", "LEARNING_PATH_NOT_FOUND")(learning_path_id)


CourseIdParam = Annotated[int, Depends(course_id_path)]
VersionIdParam = Annotated[int, Depends(version_id_path)]
ModuleIdParam = Annotated[int, Depends(module_id_path)]
TopicIdParam = Annotated[int, Depends(topic_id_path)]
TopicItemIdParam = Annotated[int, Depends(topic_item_id_path)]
LearningPathIdParam = Annotated[int, Depends(learning_path_id_path)]


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
    """Per-client-IP limit. ``limit_setting`` names the Settings field holding the limit."""

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
        if not auth.can(scope.value):  # a permission from the token; a super admin holds them all
            raise PermissionDeniedError()
        return auth

    return dependency


RequireAuthor = Annotated[AccessTokenClaims, Depends(require_scope(Scope.CONTENT_AUTHOR))]


# Reading. Course and learning-path listings (titles, status) need only a sign-in: every role names courses somewhere
# (requests, prices, job eligibility). A course's content needs a reader permission; an unpublished version or path is
# for its authors and reviewers only. Permissions from the token (user-management's catalog; per-person editable):
#   catalog.read (students, staff, heads)   catalog.browse (staff, heads)   content.author / content.review   platform staff
_PLATFORM_ROLES = frozenset({"admin", "super_admin"})


def sees_drafts(auth: AccessTokenClaims) -> bool:
    return auth.can(Scope.CONTENT_AUTHOR.value) or auth.can(Scope.CONTENT_REVIEW.value)


def can_read_content(auth: AccessTokenClaims) -> bool:
    return sees_drafts(auth) or auth.role in _PLATFORM_ROLES or auth.has_scope("catalog.read") or auth.has_scope("catalog.browse")


def require_reader(auth: CurrentAuth) -> AccessTokenClaims:
    if not can_read_content(auth):
        raise PermissionDeniedError("You don't have access to course content.", code="CONTENT_NOT_ALLOWED")
    return auth


def require_drafts(auth: CurrentAuth) -> AccessTokenClaims:
    if not sees_drafts(auth):
        raise PermissionDeniedError()
    return auth


RequireReader = Annotated[AccessTokenClaims, Depends(require_reader)]
RequireDraftReader = Annotated[AccessTokenClaims, Depends(require_drafts)]
RequireReviewer = Annotated[AccessTokenClaims, Depends(require_scope(Scope.CONTENT_REVIEW))]
