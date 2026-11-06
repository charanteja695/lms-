"""Exercises the real chain (no dependency override): JWKS signature verification via
lms_common.auth.JWKSVerifier, then revocation via lms_common.access_state against fakeredis.
Everything else in this suite overrides ``_authenticate`` directly for speed; this file proves
the override is standing in for something that actually works end to end.
"""

import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from jwt.algorithms import RSAAlgorithm
from lms_common.auth import JWKSVerifier

import app.api.deps as deps

ISSUER = "lms-user-management"
AUDIENCE = "lms"


def _key_pair() -> tuple[str, dict[str, object]]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update({"kid": "test-key-1", "use": "sig", "alg": "RS256"})
    return private_pem, jwk


PRIVATE_KEY, JWK = _key_pair()


def _sign(claims: dict[str, object]) -> str:
    now = datetime.now(UTC)
    payload = {
        "iss": ISSUER, "aud": AUDIENCE, "sub": "358672738860850316", "sid": "358672738835009029",
        "role": "admin", "org": None, "org_type": None, "scopes": ["content.author"], "ver": 0,
        "type": "access", "jti": "abc123", "iat": now, "nbf": now, "exp": now + timedelta(minutes=15),
        **claims,
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256", headers={"kid": JWK["kid"]})


@pytest.fixture(autouse=True)
def _real_verifier(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fetch_jwks() -> dict[str, object]:
        return {"keys": [JWK]}

    verifier = JWKSVerifier(issuer=ISSUER, audience=AUDIENCE, fetch_jwks=fetch_jwks)
    monkeypatch.setattr(deps, "get_verifier", lambda: verifier)


_COURSE_PAYLOAD = {"title": "A Course", "slug": "wiring-test-course", "summary": "Ten characters or more of summary."}


async def test_a_correctly_signed_token_is_accepted(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/courses", json=_COURSE_PAYLOAD, headers={"Authorization": f"Bearer {_sign({})}"}
        )
    assert response.status_code == 201


async def test_a_revoked_session_is_rejected(app) -> None:
    await app.state.redis.set("lms:access:session:358672738835009029", "1")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/courses", json=_COURSE_PAYLOAD, headers={"Authorization": f"Bearer {_sign({})}"}
        )
    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_REVOKED"


async def test_an_expired_token_is_rejected(app) -> None:
    now = datetime.now(UTC)
    token = _sign({"exp": now - timedelta(minutes=1)})
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/courses", json=_COURSE_PAYLOAD, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"
