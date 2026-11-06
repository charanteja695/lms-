"""Browser cookie sessions, revocation shared with other services, and signing-key rotation."""

from collections.abc import Iterator
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from httpx import AsyncClient
from lms_common.access_state import TokenIdentity, is_token_revoked

from app.core.config import get_settings
from app.core.ids import new_public_id
from app.core.security import TokenError, create_access_token, decode_access_token, get_jwks
from app.worker.runner import WorkerContext, run_once
from tests.conftest import API, NEW_PASSWORD, Hierarchy

COOKIE = {"X-Session-Transport": "cookie"}


def _identity(access_token: str) -> TokenIdentity:
    payload = jwt.decode(access_token, options={"verify_signature": False})
    return TokenIdentity(
        session_id=payload["sid"],
        user_id=payload["sub"],
        organization_id=payload.get("org"),
        token_version=payload["ver"],
        issued_at=payload["iat"],
    )


async def _relay(app: FastAPI) -> None:
    settings = get_settings()
    await run_once(
        WorkerContext(
            settings=settings,
            sessionmaker=app.state.sessionmaker,
            redis=app.state.redis,
            email_sender=app.state.email_sender,
        )
    )


# ---------------------------------------------------------------- cookie transport


async def test_browser_session_keeps_refresh_token_in_http_only_cookie(
    client: AsyncClient, hierarchy: Hierarchy
) -> None:
    response = await client.post(
        f"{API}/auth/login", json={"identifier": "student1", "password": NEW_PASSWORD}, headers=COOKIE
    )
    assert response.status_code == 200, response.text
    assert response.json()["token"]["refresh_token"] is None
    set_cookie = response.headers["set-cookie"].lower()
    assert (
        "lms_refresh=" in set_cookie
        and "httponly" in set_cookie
        and "samesite=strict" in set_cookie
        and "path=/api/v1/auth" in set_cookie
    )

    # Without the transport header the cookie is ignored (CSRF guard).
    assert (await client.post(f"{API}/auth/refresh-token")).json()["code"] == "INVALID_REFRESH_TOKEN"

    refreshed = await client.post(f"{API}/auth/refresh-token", headers=COOKIE)
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["token"]["refresh_token"] is None
    headers = {"Authorization": f"Bearer {refreshed.json()['token']['access_token']}", **COOKIE}

    logout = await client.post(f"{API}/auth/logout", headers=headers)
    assert logout.status_code == 200
    assert 'lms_refresh=""' in logout.headers["set-cookie"] or "max-age=0" in logout.headers["set-cookie"].lower()
    assert (await client.post(f"{API}/auth/refresh-token", headers=COOKIE)).status_code == 401


async def test_body_transport_is_unchanged_for_other_clients(client: AsyncClient, hierarchy: Hierarchy) -> None:
    body = (await client.post(f"{API}/auth/login", json={"identifier": "staff1", "password": NEW_PASSWORD})).json()
    assert body["token"]["refresh_token"]
    refreshed = await client.post(f"{API}/auth/refresh-token", json={"refresh_token": body["token"]["refresh_token"]})
    assert refreshed.status_code == 200 and refreshed.json()["token"]["refresh_token"]


# ---------------------------------------------------------------- access state for other services


async def test_suspending_a_user_revokes_their_tokens_for_other_services(
    client: AsyncClient, app: FastAPI, hierarchy: Hierarchy
) -> None:
    identity = _identity(hierarchy.student["Authorization"].removeprefix("Bearer "))
    redis, settings = app.state.redis, get_settings()
    await _relay(app)
    assert await is_token_revoked(redis, identity, key_prefix=settings.ACCESS_STATE_KEY_PREFIX) is False

    response = await client.patch(
        f"{API}/users/{hierarchy.student_id}/status", json={"status": "suspended"}, headers=hierarchy.head
    )
    assert response.status_code == 200, response.text
    await _relay(app)
    assert await is_token_revoked(redis, identity, key_prefix=settings.ACCESS_STATE_KEY_PREFIX) is True


async def test_signing_out_one_device_revokes_only_that_session(
    client: AsyncClient, app: FastAPI, hierarchy: Hierarchy
) -> None:
    other = (await client.post(f"{API}/auth/login", json={"identifier": "staff1", "password": NEW_PASSWORD})).json()
    this_device = _identity(hierarchy.staff["Authorization"].removeprefix("Bearer "))
    other_device = _identity(other["token"]["access_token"])

    assert (await client.post(f"{API}/auth/logout", headers=hierarchy.staff)).status_code == 200
    await _relay(app)
    redis, settings = app.state.redis, get_settings()
    assert await is_token_revoked(redis, this_device, key_prefix=settings.ACCESS_STATE_KEY_PREFIX) is True
    assert await is_token_revoked(redis, other_device, key_prefix=settings.ACCESS_STATE_KEY_PREFIX) is False


async def test_suspending_an_institution_revokes_all_member_tokens(
    client: AsyncClient, app: FastAPI, hierarchy: Hierarchy
) -> None:
    identity = _identity(hierarchy.staff["Authorization"].removeprefix("Bearer "))
    response = await client.patch(
        f"{API}/institutions/{hierarchy.organization_id}/status", json={"status": "suspended"}, headers=hierarchy.admin
    )
    assert response.status_code == 200, response.text
    await _relay(app)
    assert await is_token_revoked(app.state.redis, identity, key_prefix=get_settings().ACCESS_STATE_KEY_PREFIX) is True


# ---------------------------------------------------------------- signing-key rotation


def _write_key_pair(directory: Path, name: str) -> tuple[Path, Path]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = directory / f"{name}.pem"
    public = directory / f"{name}.pub.pem"
    private.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    public.write_bytes(
        key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    return private, public


@pytest.fixture
def rs256(tmp_path: Path) -> Iterator[dict[str, Path]]:
    settings = get_settings()
    names = [
        "JWT_ALGORITHM",
        "JWT_PRIVATE_KEY_FILE",
        "JWT_PUBLIC_KEY_FILE",
        "JWT_KEY_ID",
        "JWT_PREVIOUS_PUBLIC_KEY_FILE",
        "JWT_PREVIOUS_KEY_ID",
    ]
    original = {name: getattr(settings, name) for name in names}
    old_private, old_public = _write_key_pair(tmp_path, "old")
    new_private, new_public = _write_key_pair(tmp_path, "new")
    settings.JWT_ALGORITHM = "RS256"
    try:
        yield {
            "old_private": old_private,
            "old_public": old_public,
            "new_private": new_private,
            "new_public": new_public,
        }
    finally:
        for name, value in original.items():
            setattr(settings, name, value)


def test_previous_signing_key_stays_valid_during_rotation(rs256: dict[str, Path]) -> None:
    settings = get_settings()
    user_id = new_public_id()
    settings.JWT_PRIVATE_KEY_FILE, settings.JWT_PUBLIC_KEY_FILE, settings.JWT_KEY_ID = (
        rs256["old_private"],
        rs256["old_public"],
        "key-1",
    )
    old_token, _ = create_access_token(
        user_id=user_id, session_id=new_public_id(), role="staff", organization_id=None, token_version=0
    )

    # Rotate: new key signs, old public key is still published and accepted.
    settings.JWT_PRIVATE_KEY_FILE, settings.JWT_PUBLIC_KEY_FILE, settings.JWT_KEY_ID = (
        rs256["new_private"],
        rs256["new_public"],
        "key-2",
    )
    settings.JWT_PREVIOUS_PUBLIC_KEY_FILE, settings.JWT_PREVIOUS_KEY_ID = rs256["old_public"], "key-1"
    new_token, _ = create_access_token(
        user_id=user_id, session_id=new_public_id(), role="staff", organization_id=None, token_version=0
    )
    assert decode_access_token(old_token).user_id == user_id
    assert decode_access_token(new_token).user_id == user_id
    assert sorted(key["kid"] for key in get_jwks()["keys"]) == ["key-1", "key-2"]

    # Retire the old key: its tokens stop working.
    settings.JWT_PREVIOUS_PUBLIC_KEY_FILE, settings.JWT_PREVIOUS_KEY_ID = None, None
    with pytest.raises(TokenError):
        decode_access_token(old_token)
