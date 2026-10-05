"""FastAPI dependencies: database, request context, authentication and authorisation.

Every request's bearer token is verified against user-management's JWKS, then checked against the Redis access-state keys so a suspended user loses
access within seconds, without this service calling user-management per request. The payment gateway's webhook is the one unauthenticated route:
it is verified by its HMAC signature instead (see app/gateways/payment.py).
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
from app.gateways.payment import PaymentGateway
from app.permissions.policy import can_manage_billing, is_billing_contact
from app.permissions.roles import Role
from app.services.rate_limiter import RateLimiter

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_redis(request: Request) -> Redis:
    return cast(Redis, request.app.state.redis)


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
        session_id=str(claims.session_id), user_id=str(claims.user_id), organization_id=str(claims.organization_id) if claims.organization_id else None,
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


RequireBillingAdmin = Annotated[AccessTokenClaims, Depends(_require(can_manage_billing, "Only platform billing managers can do this.", "PERMISSION_DENIED"))]
RequireBillingContact = Annotated[
    AccessTokenClaims, Depends(_require(lambda a: is_billing_contact(a) or can_manage_billing(a), "Only an institution head, an employer admin or a billing manager can do this.", "PERMISSION_DENIED"))
]
RequireEmployerAdmin = Annotated[AccessTokenClaims, Depends(_require(lambda a: a.role == Role.EMPLOYER_ADMIN and a.organization_id is not None, "Only an employer admin can buy a plan.", "EMPLOYER_ADMINS_ONLY"))]


def get_payment_gateway(settings: SettingsDep) -> PaymentGateway:
    return PaymentGateway(settings)


PaymentGatewayDep = Annotated[PaymentGateway, Depends(get_payment_gateway)]


def _id_path(label: str, code: str) -> Callable[..., Awaitable[int]]:
    async def parse(value: str) -> int:
        number = parse_public_id(value)
        if number is None:
            raise NotFoundError(f"{label} not found.", code=code)
        return number

    return parse


async def invoice_id_path(invoice_id: Annotated[str, Path()]) -> int:
    return await _id_path("Invoice", "INVOICE_NOT_FOUND")(invoice_id)


async def quote_id_path(quote_id: Annotated[str, Path()]) -> int:
    return await _id_path("Quote", "QUOTE_NOT_FOUND")(quote_id)


async def price_id_path(price_id: Annotated[str, Path()]) -> int:
    return await _id_path("Price", "PRICE_NOT_FOUND")(price_id)


async def org_id_path(org_id: Annotated[str, Path()]) -> int:
    return await _id_path("Organisation", "ORGANIZATION_NOT_FOUND")(org_id)


InvoiceIdParam = Annotated[int, Depends(invoice_id_path)]
QuoteIdParam = Annotated[int, Depends(quote_id_path)]
PriceIdParam = Annotated[int, Depends(price_id_path)]
OrgIdParam = Annotated[int, Depends(org_id_path)]


def rate_limit_user(scope: str, limit_setting: str, window_seconds: int) -> Callable[..., Awaitable[None]]:
    async def dependency(auth: CurrentAuth, settings: SettingsDep, limiter: RateLimiterDep) -> None:
        await limiter.hit(f"{scope}:user:{auth.user_id}", limit=getattr(settings, limit_setting), window_seconds=window_seconds)

    return dependency


WriteRateLimit = Depends(rate_limit_user("billing-write", "WRITE_RATE_LIMIT_PER_USER_PER_MINUTE", 60))
