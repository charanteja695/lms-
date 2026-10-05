"""Verify access tokens issued by user-management, without ever holding its signing key.

Every other service depends on this instead of re-implementing JWT verification. It never calls
user-management per request: the public keys are fetched from ``/.well-known/jwks.json``, cached
by ``kid`` for ``cache_seconds``, and refetched once if an unknown ``kid`` shows up (covers key
rotation without a restart). Combine with :mod:`lms_common.access_state` to also reject tokens
that were valid when signed but have since been revoked.
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any

import jwt
from jwt.algorithms import RSAAlgorithm

from lms_common.auth.claims import AccessTokenClaims
from lms_common.ids import parse_public_id

ACCESS_TOKEN_TYPE = "access"

JWKSFetcher = Callable[[], Awaitable[dict[str, Any]]]


class TokenError(Exception):
    """Raised when an access token is missing, malformed, expired, tampered with, or unknown."""


class JWKSVerifier:
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        fetch_jwks: JWKSFetcher,
        leeway_seconds: int = 10,
        cache_seconds: int = 300,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._fetch_jwks = fetch_jwks
        self._leeway_seconds = leeway_seconds
        self._cache_seconds = cache_seconds
        self._keys: dict[str, str] = {}
        self._fetched_at: float = 0.0

    async def _key_for(self, kid: str) -> str | None:
        now = time.monotonic()
        stale = now - self._fetched_at > self._cache_seconds
        if kid not in self._keys or stale:
            await self._refresh()
        return self._keys.get(kid)

    async def _refresh(self) -> None:
        document = await self._fetch_jwks()
        keys: dict[str, str] = {}
        for jwk in document.get("keys", []):
            kid = jwk.get("kid")
            if not kid:
                continue
            keys[kid] = RSAAlgorithm.from_jwk(jwk)  # type: ignore[assignment]
        self._keys = keys
        self._fetched_at = time.monotonic()

    async def verify(self, token: str) -> AccessTokenClaims:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenError(str(exc)) from exc

        kid = str(header.get("kid") or "")
        key = await self._key_for(kid)
        if key is None:
            raise TokenError("Unknown signing key")

        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=["RS256"],  # pinned: never trust the header's alg
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._leeway_seconds,
                options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub", "sid", "ver", "jti", "type"]},
            )
        except jwt.PyJWTError as exc:
            raise TokenError(str(exc)) from exc

        if payload.get("type") != ACCESS_TOKEN_TYPE:
            raise TokenError("Unexpected token type")

        try:
            user_id = parse_public_id(payload["sub"])
            session_id = parse_public_id(payload["sid"])
            organization_id = parse_public_id(payload["org"]) if payload.get("org") else None
            if user_id is None or session_id is None or (payload.get("org") and organization_id is None):
                raise TokenError("Malformed identifiers")
            return AccessTokenClaims(
                user_id=user_id,
                session_id=session_id,
                role=str(payload["role"]),
                organization_id=organization_id,
                organization_type=payload.get("org_type"),
                scopes=tuple(payload.get("scopes", [])),
                token_version=int(payload["ver"]),
                token_id=str(payload["jti"]),
                issued_at=int(payload["iat"]),
                expires_at=payload["exp"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise TokenError("Malformed token claims") from exc
