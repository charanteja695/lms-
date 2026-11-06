"""Refresh token transport for browsers.

Web clients send ``X-Session-Transport: cookie`` on login, two-factor verify, refresh and logout. The refresh
token is then set as an httpOnly, SameSite=Strict cookie scoped to the auth path and omitted from the JSON body,
so page scripts can never read it. Other clients (mobile apps, services) keep receiving it in the body.

The custom header is also the CSRF guard: a cross-site form cannot send it, and a cross-site script cannot
send it without a CORS preflight that this API rejects.
"""

from fastapi import Request, Response

from app.core.config import Settings
from app.schemas.auth import TokenOut

TRANSPORT_HEADER = "x-session-transport"


def wants_cookie(request: Request) -> bool:
    return request.headers.get(TRANSPORT_HEADER, "").lower() == "cookie"


def deliver(request: Request, response: Response, token: TokenOut, settings: Settings) -> TokenOut:
    if not wants_cookie(request) or token.refresh_token is None:
        return token
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        token.refresh_token,
        max_age=token.refresh_expires_in,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )
    return token.model_copy(update={"refresh_token": None})


def read(request: Request, settings: Settings) -> str | None:
    return request.cookies.get(settings.REFRESH_COOKIE_NAME) if wants_cookie(request) else None


def clear(request: Request, response: Response, settings: Settings) -> None:
    if wants_cookie(request):
        response.delete_cookie(
            settings.REFRESH_COOKIE_NAME,
            path=settings.REFRESH_COOKIE_PATH,
            domain=settings.REFRESH_COOKIE_DOMAIN,
            secure=settings.REFRESH_COOKIE_SECURE,
            httponly=True,
            samesite=settings.REFRESH_COOKIE_SAMESITE,
        )
