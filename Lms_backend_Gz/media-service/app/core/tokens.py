"""Opaque playback tokens: generated once, stored only as a salted hash (same pattern as
user-management's refresh tokens), so a leaked database dump can't be replayed as a token."""

import hashlib
import hmac
import secrets

from app.core.config import get_settings


def generate_secure_token(num_bytes: int = 32) -> str:
    return secrets.token_urlsafe(num_bytes)


def hash_token(value: str) -> str:
    secret = get_settings().TOKEN_HASH_SECRET.get_secret_value().encode()
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()
