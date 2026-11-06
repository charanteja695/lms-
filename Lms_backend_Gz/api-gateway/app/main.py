import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import health, proxy
from app.core.config import ROUTES_FILE, Settings, get_settings
from app.core.error_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.proxy.routes import RouteTable
from app.redis_client import build_redis


def build_http_client() -> httpx.AsyncClient:
    """One pooled client for every service. No redirects are followed (a service's 3xx goes to the caller as it is) and no cookies are kept: the gateway is stateless."""
    return httpx.AsyncClient(limits=httpx.Limits(max_connections=500, max_keepalive_connections=100), follow_redirects=False, trust_env=False)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.redis = build_redis(settings)
    app.state.http = build_http_client()
    try:
        yield
    finally:
        await app.state.http.aclose()
        await app.state.redis.aclose()


def load_route_table() -> RouteTable:
    return RouteTable.from_json(json.loads(ROUTES_FILE.read_text(encoding="utf-8"))["rules"])


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.LOG_LEVEL, settings.LOG_JSON)

    app = FastAPI(
        title="LMS API Gateway",
        version=settings.APP_VERSION,
        description="The platform's single public entry point: routes each path to its service by a generated route table, refuses internal paths, checks a bearer token when one is "
        "sent, rate-limits per user or IP, applies CORS once and stamps every request with an id. No business logic.",
        docs_url=None, redoc_url=None, openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.route_table = load_route_table()
    app.state.upstreams = settings.upstreams()
    register_exception_handlers(app)

    # Middleware added last runs first. No compression here: the services already compress, and a second pass would double-encode their bodies.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)
    if settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key", "X-Signature"],
            expose_headers=["X-Request-ID", "Retry-After", "Content-Disposition"],
            max_age=600,
        )
    app.add_middleware(SecurityHeadersMiddleware, enable_hsts=settings.is_production_like)
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health.router)
    app.include_router(proxy.router)
    return app


app = create_app()
