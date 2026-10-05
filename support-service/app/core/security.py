"""Token verification only: this service never issues access tokens (see lms-backend/README.md §2).

Signatures are checked against user-management's published JWKS; revocation is checked
separately against the Redis keys user-management maintains (see app/api/deps.py). Only the
admin API (prompts, quotas, logs, model routing) uses this — the completion/embedding/speech
API is called by other services with the internal service token instead.
"""

from functools import lru_cache
from typing import Any, cast

import httpx
from lms_common.auth import AccessTokenClaims, JWKSVerifier, TokenError

from app.core.config import Settings, get_settings

__all__ = ["AccessTokenClaims", "TokenError", "get_verifier"]


async def _fetch_jwks(settings: Settings) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=settings.JWKS_FETCH_TIMEOUT_SECONDS) as client:
        response = await client.get(settings.USER_MANAGEMENT_JWKS_URL)
        response.raise_for_status()
        return cast("dict[str, Any]", response.json())


@lru_cache
def get_verifier() -> JWKSVerifier:
    settings = get_settings()
    return JWKSVerifier(
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
        fetch_jwks=lambda: _fetch_jwks(settings),
        leeway_seconds=settings.JWT_LEEWAY_SECONDS,
        cache_seconds=settings.JWKS_CACHE_SECONDS,
    )
