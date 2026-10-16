"""Cryptographic primitives: password hashing, opaque token hashing, OTPs and JWTs."""

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jwt
from anyio import CapacityLimiter, to_thread
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings
from app.core.ids import parse_public_id
from app.core.time import utcnow

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

ACCESS_TOKEN_TYPE = "access"


# --------------------------------------------------------------------------- passwords


@lru_cache
def _password_hasher() -> PasswordHasher:
    settings = get_settings()
    return PasswordHasher(
        time_cost=settings.ARGON2_TIME_COST,
        memory_cost=settings.ARGON2_MEMORY_COST_KIB,
        parallelism=settings.ARGON2_PARALLELISM,
    )


@lru_cache
def _dummy_hash() -> str:
    return _password_hasher().hash(secrets.token_urlsafe(32))


_hash_limiters: dict[int, CapacityLimiter] = {}


def _hash_limiter() -> CapacityLimiter:
    """Bounds concurrent Argon2 work per process (one limiter per event loop)."""
    loop_id = id(asyncio.get_running_loop())
    limiter = _hash_limiters.get(loop_id)
    if limiter is None:
        limiter = CapacityLimiter(get_settings().PASSWORD_HASH_CONCURRENCY)
        _hash_limiters.clear()
        _hash_limiters[loop_id] = limiter
    return limiter


async def hash_password(password: str) -> str:
    # Argon2 is deliberately CPU/memory heavy; keep it off the event loop and bounded.
    return await to_thread.run_sync(_password_hasher().hash, password, limiter=_hash_limiter())


async def verify_password(password_hash: str, password: str) -> tuple[bool, bool]:
    """Return ``(is_valid, needs_rehash)``."""

    def _verify() -> tuple[bool, bool]:
        hasher = _password_hasher()
        try:
            hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False, False
        return True, hasher.check_needs_rehash(password_hash)

    return await to_thread.run_sync(_verify, limiter=_hash_limiter())


async def spend_password_verification_time(password: str) -> None:
    """Verify against a dummy hash so unknown accounts respond as slowly as known ones."""
    await to_thread.run_sync(_dummy_hash, limiter=_hash_limiter())
    await verify_password(_dummy_hash(), password)


# --------------------------------------------------------------------------- opaque tokens


def generate_secure_token(num_bytes: int = 48) -> str:
    return secrets.token_urlsafe(num_bytes)


def generate_otp(length: int) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def hash_token(value: str) -> str:
    """HMAC-SHA256 with a server-side pepper. Used for refresh tokens, OTPs and reset tokens."""
    secret = get_settings().TOKEN_HASH_SECRET.get_secret_value().encode()
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()


_TEMPORARY_PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no look-alikes (0/O, 1/l/I)


def generate_temporary_password(min_length: int) -> str:
    """Readable one-time password such as ``Kp7m-X3qd-9Hwt``: groups of 4, at least ~70 bits of entropy,
    always containing lower case, upper case, a digit and a symbol. The user must change it at first sign-in."""
    groups = max(3, -(-min_length // 5))
    while True:
        value = "-".join("".join(secrets.choice(_TEMPORARY_PASSWORD_ALPHABET) for _ in range(4)) for _ in range(groups))
        if any(c.islower() for c in value) and any(c.isupper() for c in value) and any(c.isdigit() for c in value):
            return value


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


# --------------------------------------------------------------------------- JWT


class TokenError(Exception):
    """Raised when an access token is missing, malformed, expired or tampered with."""


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """All identifiers are public ids (``user_id``, ``session_id``, ``organization_id``)."""

    user_id: int
    session_id: int
    role: str
    organization_id: int | None
    token_version: int
    token_id: str
    expires_at: datetime
    issued_at: int = 0


@lru_cache
def _read_key_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _signing_key() -> str:
    settings = get_settings()
    if settings.JWT_ALGORITHM == "RS256":
        assert settings.JWT_PRIVATE_KEY_FILE is not None
        return _read_key_file(settings.JWT_PRIVATE_KEY_FILE)
    return settings.JWT_SECRET_KEY.get_secret_value()


def _verification_keys() -> dict[str, str]:
    """``kid`` -> key. With RS256 the previous key stays valid during rotation."""
    settings = get_settings()
    if settings.JWT_ALGORITHM != "RS256":
        return {settings.JWT_KEY_ID: settings.JWT_SECRET_KEY.get_secret_value()}
    assert settings.JWT_PUBLIC_KEY_FILE is not None
    keys = {settings.JWT_KEY_ID: _read_key_file(settings.JWT_PUBLIC_KEY_FILE)}
    if settings.JWT_PREVIOUS_PUBLIC_KEY_FILE and settings.JWT_PREVIOUS_KEY_ID:
        keys[settings.JWT_PREVIOUS_KEY_ID] = _read_key_file(settings.JWT_PREVIOUS_PUBLIC_KEY_FILE)
    return keys


def create_access_token(
    *,
    user_id: int,
    session_id: int,
    role: str,
    organization_id: int | None,
    token_version: int,
    organization_type: str | None = None,
    scopes: list[str] | None = None,
    admin_organization_ids: list[int] | None = None,
) -> tuple[str, int]:
    """Return ``(token, expires_in_seconds)``."""
    settings = get_settings()
    now = utcnow()
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    payload: dict[str, Any] = {
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "sub": str(user_id),
        "sid": str(session_id),
        "role": role,
        "org": str(organization_id) if organization_id else None,
        "org_type": organization_type,
        "scopes": scopes or [],
        # an admin's institutions: other services limit accounts.manage-style permissions to these
        **({"admin_orgs": [str(i) for i in admin_organization_ids]} if admin_organization_ids else {}),
        "ver": token_version,
        "type": ACCESS_TOKEN_TYPE,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(
        payload,
        _signing_key(),
        algorithm=settings.JWT_ALGORITHM,
        headers={"kid": settings.JWT_KEY_ID},
    )
    return token, expires_in


def decode_access_token(token: str) -> AccessTokenClaims:
    settings = get_settings()
    try:
        key = _verification_keys().get(str(jwt.get_unverified_header(token).get("kid")))
        if key is None:
            raise TokenError("Unknown signing key")
        payload = jwt.decode(
            token,
            key,
            algorithms=[settings.JWT_ALGORITHM],  # pinned: never trust the header's alg
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            leeway=settings.JWT_LEEWAY_SECONDS,
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
            token_version=int(payload["ver"]),
            token_id=str(payload["jti"]),
            issued_at=int(payload["iat"]),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TokenError("Malformed token claims") from exc


def get_jwks() -> dict[str, list[dict[str, Any]]]:
    """Public signing keys for other services. Empty for HS256 (shared secrets are never published)."""
    settings = get_settings()
    if settings.JWT_ALGORITHM != "RS256":
        return {"keys": []}
    from jwt.algorithms import RSAAlgorithm

    keys = []
    for kid, pem in _verification_keys().items():
        jwk = json.loads(RSAAlgorithm.to_jwk(RSAAlgorithm(RSAAlgorithm.SHA256).prepare_key(pem)))
        jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
        keys.append(jwk)
    return {"keys": keys}


# --------------------------------------------------------------------------- secrets at rest (TOTP)


@lru_cache
def _fernet() -> "Fernet":
    from cryptography.fernet import Fernet

    settings = get_settings()
    if settings.MFA_ENCRYPTION_KEY is not None:
        key = settings.MFA_ENCRYPTION_KEY.get_secret_value().encode()
    else:  # local/test only (production requires MFA_ENCRYPTION_KEY)
        digest = hashlib.sha256(b"lms-mfa:" + settings.TOKEN_HASH_SECRET.get_secret_value().encode()).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
