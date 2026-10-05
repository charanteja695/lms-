import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from lms_common.auth import JWKSVerifier, TokenError

ISSUER = "lms-user-management"
AUDIENCE = "lms"
_key_counter = 0


def _key_pair() -> tuple[str, dict[str, object]]:
    global _key_counter
    _key_counter += 1
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update({"kid": f"key-{_key_counter}", "use": "sig", "alg": "RS256"})
    return private_pem, jwk


PRIVATE_KEY, JWK = _key_pair()


def _sign(claims: dict[str, object], *, kid: str = JWK["kid"], key: str = PRIVATE_KEY) -> str:
    now = datetime.now(UTC)
    payload = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "358672738860850316",
        "sid": "358672738835009029",
        "role": "staff",
        "org": "358672738414054064",
        "org_type": "institution",
        "scopes": [],
        "ver": 0,
        "type": "access",
        "jti": "abc123",
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=15),
        **claims,
    }
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": kid})


async def _fetch_jwks() -> dict[str, object]:
    return {"keys": [JWK]}


def _verifier(fetch=_fetch_jwks) -> JWKSVerifier:
    return JWKSVerifier(issuer=ISSUER, audience=AUDIENCE, fetch_jwks=fetch)


async def test_verifies_a_correctly_signed_token() -> None:
    claims = await _verifier().verify(_sign({}))
    assert claims.user_id == 358672738860850316
    assert claims.role == "staff"
    assert claims.organization_type == "institution"


async def test_rejects_unknown_signing_key() -> None:
    other_private, _ = _key_pair()
    token = _sign({}, kid="rogue-key", key=other_private)
    with pytest.raises(TokenError):
        await _verifier().verify(token)


async def test_rejects_expired_token() -> None:
    now = datetime.now(UTC)
    token = _sign({"exp": now - timedelta(minutes=1)})
    with pytest.raises(TokenError):
        await _verifier().verify(token)


async def test_rejects_wrong_audience() -> None:
    token = _sign({"aud": "someone-else"})
    with pytest.raises(TokenError):
        await _verifier().verify(token)


async def test_rejects_non_access_token_type() -> None:
    token = _sign({"type": "refresh"})
    with pytest.raises(TokenError):
        await _verifier().verify(token)


async def test_refetches_once_for_a_new_key_id_after_rotation() -> None:
    new_private, new_jwk = _key_pair()
    calls = {"count": 0}

    async def rotating_fetch() -> dict[str, object]:
        calls["count"] += 1
        # The old key is retired once the caller has rotated: only the new key is published.
        return {"keys": [new_jwk]}

    token = _sign({}, kid=new_jwk["kid"], key=new_private)
    claims = await _verifier(fetch=rotating_fetch).verify(token)
    assert claims.user_id == 358672738860850316
    assert calls["count"] == 1
