"""FastAPI dependencies: database, request context, services and the authentication chain."""

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import BackgroundTasks, Depends, Path, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.context import RequestContext
from app.core.exceptions import AuthenticationError, NotFoundError, PermissionDeniedError
from app.core.ids import EXAMPLE_ORGANIZATION_ID, EXAMPLE_SESSION_ID, EXAMPLE_USER_ID, parse_public_id
from app.core.security import TokenError, decode_access_token
from app.core.time import utcnow
from app.models.institution import Institution
from app.models.mfa import UserMfa
from app.models.session import UserSession
from app.models.user import User
from app.notifications.notifier import Notifier
from app.permissions.roles import OrganizationType, Role
from app.services.access_service import check_institution_active, ensure_user_active
from app.services.auth_service import AuthService
from app.services.institution_service import InstitutionService
from app.services.mfa_service import MfaService
from app.services.permission_service import PermissionService
from app.services.rate_limiter import RateLimiter
from app.services.signup_service import SignupService
from app.services.user_service import UserService

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


async def user_id_path(user_id: Annotated[str, Path(examples=[EXAMPLE_USER_ID])]) -> int:
    return _path_id("User", "USER_NOT_FOUND")(user_id)


async def admin_id_path(user_id: Annotated[str, Path(examples=[EXAMPLE_USER_ID])]) -> int:
    return _path_id("Admin", "USER_NOT_FOUND")(user_id)


async def organization_id_path(organization_id: Annotated[str, Path(examples=[EXAMPLE_ORGANIZATION_ID])]) -> int:
    return _path_id("Institution", "INSTITUTION_NOT_FOUND")(organization_id)


async def session_id_path(session_id: Annotated[str, Path(examples=[EXAMPLE_SESSION_ID])]) -> int:
    return _path_id("Session", "SESSION_NOT_FOUND")(session_id)


UserIdParam = Annotated[int, Depends(user_id_path)]
AdminIdParam = Annotated[int, Depends(admin_id_path)]
OrganizationIdParam = Annotated[int, Depends(organization_id_path)]
SessionIdParam = Annotated[int, Depends(session_id_path)]


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


def get_notifier(request: Request, background_tasks: BackgroundTasks, settings: SettingsDep) -> Notifier:
    return Notifier(background_tasks, request.app.state.email_sender, settings)


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


@dataclass(frozen=True, slots=True)
class AuthContext:
    user: User
    session: UserSession
    institution: Institution | None
    mfa_enabled: bool


_bearer_scheme = HTTPBearer(auto_error=False, description="Access token from POST /auth/login")


async def _authenticate(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> AuthContext:
    """Authentication -> token valid -> session live -> user active -> institution active."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Log in to continue.", code="NOT_AUTHENTICATED")

    try:
        claims = decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise AuthenticationError("Your access token is invalid or has expired.", code="INVALID_TOKEN") from exc

    # One round trip: user + session + institution (this runs on every authenticated request).
    row = (
        await db.execute(
            select(User, UserSession, Institution, UserMfa.enabled_at)
            .join(UserSession, UserSession.user_id == User.id)
            .outerjoin(Institution, Institution.id == User.institution_id)
            .outerjoin(UserMfa, UserMfa.user_id == User.id)
            .where(User.public_id == claims.user_id, UserSession.public_id == claims.session_id)
        )
    ).one_or_none()
    if row is None:
        raise AuthenticationError("Your session has ended. Please log in again.", code="SESSION_REVOKED")
    user, session, institution, mfa_enabled_at = row
    if user.deleted_at is not None:
        raise AuthenticationError("Your access token is invalid or has expired.", code="INVALID_TOKEN")
    if user.token_version != claims.token_version:
        raise AuthenticationError("Your access has been revoked. Please log in again.", code="TOKEN_REVOKED")
    if session.revoked_at is not None or session.expires_at <= utcnow():
        raise AuthenticationError("Your session has ended. Please log in again.", code="SESSION_REVOKED")

    ensure_user_active(user)
    user.grant(await PermissionService(db).effective_for(user))
    return AuthContext(
        user=user,
        session=session,
        institution=check_institution_active(user, institution),
        mfa_enabled=mfa_enabled_at is not None,
    )


async def _require_password_current(auth: Annotated[AuthContext, Depends(_authenticate)]) -> AuthContext:
    if auth.user.must_change_password:
        raise PermissionDeniedError("You must change your password before continuing.", code="PASSWORD_CHANGE_REQUIRED")
    if not auth.mfa_enabled and auth.user.role in get_settings().MFA_REQUIRED_ROLES:
        raise PermissionDeniedError("Set up two-factor authentication before continuing.", code="MFA_SETUP_REQUIRED")
    return auth


# Use on every endpoint by default.
CurrentAuth = Annotated[AuthContext, Depends(_require_password_current)]
# Only for endpoints a user must reach while their account set-up is incomplete
# (temporary password or pending two-factor enrolment): me, logout, sessions, change password, MFA set-up.
CurrentAuthAllowingPasswordChange = Annotated[AuthContext, Depends(_authenticate)]


def require_roles(*roles: Role) -> Callable[..., Awaitable[AuthContext]]:
    allowed = frozenset(roles)

    async def dependency(auth: CurrentAuth) -> AuthContext:
        if auth.user.role not in allowed:
            raise PermissionDeniedError()
        return auth

    return dependency


# ------------------------------------------------------------------ services


def get_auth_service(
    db: DbSession,
    settings: SettingsDep,
    ctx: RequestCtx,
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    notifier: Annotated[Notifier, Depends(get_notifier)],
) -> AuthService:
    return AuthService(db, settings, ctx, limiter, notifier)


def get_user_service(
    db: DbSession,
    settings: SettingsDep,
    ctx: RequestCtx,
    notifier: Annotated[Notifier, Depends(get_notifier)],
) -> UserService:
    return UserService(db, settings, ctx, notifier)


def get_mfa_service(db: DbSession, settings: SettingsDep, ctx: RequestCtx) -> MfaService:
    return MfaService(db, settings, ctx)


def get_employer_service(db: DbSession, settings: SettingsDep, ctx: RequestCtx) -> InstitutionService:
    return InstitutionService(db, settings, ctx, org_type=OrganizationType.EMPLOYER)


def get_institution_service(db: DbSession, settings: SettingsDep, ctx: RequestCtx) -> InstitutionService:
    return InstitutionService(db, settings, ctx)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_signup_service(
    db: DbSession,
    settings: SettingsDep,
    ctx: RequestCtx,
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    notifier: Annotated[Notifier, Depends(get_notifier)],
) -> SignupService:
    return SignupService(db, settings, ctx, limiter, notifier)


SignupServiceDep = Annotated[SignupService, Depends(get_signup_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
MfaServiceDep = Annotated[MfaService, Depends(get_mfa_service)]
InstitutionServiceDep = Annotated[InstitutionService, Depends(get_institution_service)]
EmployerServiceDep = Annotated[InstitutionService, Depends(get_employer_service)]
