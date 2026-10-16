"""Two-factor authentication (TOTP) end to end."""

import time
from collections.abc import Iterator

import pyotp
import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.models import User
from tests.conftest import API, STRONG_PASSWORD, SUPER_ADMIN_USERNAME, Hierarchy, bearer, login


def _code(secret: str, offset_steps: int = 0) -> str:
    return pyotp.TOTP(secret).at(time.time() + offset_steps * 30)


@pytest.fixture
def mfa_required_for_admins() -> Iterator[None]:
    settings = get_settings()
    original = settings.MFA_REQUIRED_ROLES
    settings.MFA_REQUIRED_ROLES = ["super_admin", "admin"]
    try:
        yield
    finally:
        settings.MFA_REQUIRED_ROLES = original


async def _enrol(client: AsyncClient, headers: dict[str, str]) -> tuple[str, list[str]]:
    setup = await client.post(f"{API}/auth/mfa/setup", json={"password": STRONG_PASSWORD}, headers=headers)
    assert setup.status_code == 200, setup.text
    secret = setup.json()["mfa_setup"]["secret"]
    assert setup.json()["mfa_setup"]["otpauth_uri"].startswith("otpauth://totp/")
    enabled = await client.post(f"{API}/auth/mfa/enable", json={"code": _code(secret)}, headers=headers)
    assert enabled.status_code == 200, enabled.text
    return secret, enabled.json()["recovery_codes"]


async def test_enrol_then_login_requires_second_factor(client: AsyncClient, super_admin: User) -> None:
    headers = bearer(await login(client, SUPER_ADMIN_USERNAME))
    wrong_password = await client.post(f"{API}/auth/mfa/setup", json={"password": "nope"}, headers=headers)
    assert wrong_password.json()["code"] == "INVALID_CURRENT_PASSWORD"

    secret, recovery_codes = await _enrol(client, headers)
    assert len(recovery_codes) == 10
    status = (await client.get(f"{API}/auth/mfa", headers=headers)).json()["mfa"]
    assert status == {"enabled": True, "required": False, "recovery_codes_remaining": 10}

    first_step = await client.post(
        f"{API}/auth/login", json={"identifier": SUPER_ADMIN_USERNAME, "password": STRONG_PASSWORD}
    )
    body = first_step.json()
    assert body["code"] == "MFA_REQUIRED"
    assert body["token"] is None and body["user"] is None
    mfa_token = body["mfa_challenge"]["mfa_token"]

    wrong = await client.post(f"{API}/auth/mfa/verify", json={"mfa_token": mfa_token, "code": "000000"})
    assert wrong.status_code == 401
    assert wrong.json()["code"] == "INVALID_MFA_CODE"

    # The code used to enable is already spent; the next time step is accepted.
    verified = await client.post(f"{API}/auth/mfa/verify", json={"mfa_token": mfa_token, "code": _code(secret, 1)})
    assert verified.status_code == 200, verified.text
    assert verified.json()["user"]["mfa_enabled"] is True
    assert (await client.get(f"{API}/users/me", headers=bearer(verified.json()))).status_code == 200

    # A challenge works once; a code works once.
    reused = await client.post(f"{API}/auth/mfa/verify", json={"mfa_token": mfa_token, "code": _code(secret, 1)})
    assert reused.json()["code"] == "INVALID_MFA_TOKEN"


async def test_recovery_code_login_and_attempt_limit(client: AsyncClient, super_admin: User) -> None:
    headers = bearer(await login(client, SUPER_ADMIN_USERNAME))
    _, recovery_codes = await _enrol(client, headers)

    async def challenge() -> str:
        response = await client.post(
            f"{API}/auth/login", json={"identifier": SUPER_ADMIN_USERNAME, "password": STRONG_PASSWORD}
        )
        return response.json()["mfa_challenge"]["mfa_token"]

    token = await challenge()
    ok = await client.post(
        f"{API}/auth/mfa/verify", json={"mfa_token": token, "recovery_code": recovery_codes[0].upper()}
    )
    assert ok.status_code == 200, ok.text
    again = await client.post(
        f"{API}/auth/mfa/verify", json={"mfa_token": await challenge(), "recovery_code": recovery_codes[0]}
    )
    assert again.json()["code"] == "INVALID_MFA_CODE"

    token = await challenge()
    for _ in range(5):
        await client.post(f"{API}/auth/mfa/verify", json={"mfa_token": token, "code": "000000"})
    burned = await client.post(f"{API}/auth/mfa/verify", json={"mfa_token": token, "recovery_code": recovery_codes[1]})
    assert burned.json()["code"] == "INVALID_MFA_TOKEN"

    both = await client.post(
        f"{API}/auth/mfa/verify", json={"mfa_token": token, "code": "123456", "recovery_code": "abcde-fghij"}
    )
    assert both.status_code == 422


async def test_mandatory_mfa_blocks_until_enrolled(
    client: AsyncClient, super_admin: User, mfa_required_for_admins: None
) -> None:
    body = await login(client, SUPER_ADMIN_USERNAME)
    assert body["user"]["mfa_setup_required"] is True
    headers = bearer(body)
    blocked = await client.get(f"{API}/users", headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "MFA_SETUP_REQUIRED"
    assert (await client.get(f"{API}/users/me", headers=headers)).status_code == 200

    secret, _ = await _enrol(client, headers)
    assert (await client.get(f"{API}/users", headers=headers)).status_code == 200

    disable = await client.post(
        f"{API}/auth/mfa/disable", json={"password": STRONG_PASSWORD, "code": _code(secret, 1)}, headers=headers
    )
    assert disable.json()["code"] == "MFA_REQUIRED_FOR_ROLE"


async def test_disable_and_admin_reset(client: AsyncClient, hierarchy: Hierarchy) -> None:
    from tests.conftest import NEW_PASSWORD

    # The head enrols, loses the phone, and the admin resets it.
    setup = await client.post(f"{API}/auth/mfa/setup", json={"password": NEW_PASSWORD}, headers=hierarchy.head)
    secret = setup.json()["mfa_setup"]["secret"]
    await client.post(f"{API}/auth/mfa/enable", json={"code": _code(secret)}, headers=hierarchy.head)

    reset = await client.post(f"{API}/users/{hierarchy.head_id}/mfa/reset", headers=hierarchy.admin)
    assert reset.status_code == 200, reset.text
    assert (await client.get(f"{API}/users/me", headers=hierarchy.head)).status_code == 401  # signed out
    relogin = await login(client, "head1", NEW_PASSWORD)
    assert relogin["user"]["mfa_enabled"] is False

    # Staff cannot reset anyone's two-factor authentication.
    denied = await client.post(f"{API}/users/{hierarchy.student_id}/mfa/reset", headers=hierarchy.staff)
    assert denied.status_code == 403

    # Voluntary disable needs password and a code.
    headers = bearer(relogin)
    setup = await client.post(f"{API}/auth/mfa/setup", json={"password": NEW_PASSWORD}, headers=headers)
    secret = setup.json()["mfa_setup"]["secret"]
    await client.post(f"{API}/auth/mfa/enable", json={"code": _code(secret)}, headers=headers)
    off = await client.post(
        f"{API}/auth/mfa/disable", json={"password": NEW_PASSWORD, "code": _code(secret, 1)}, headers=headers
    )
    assert off.status_code == 200, off.text


def _fixed_code(value: str | None) -> Iterator[str | None]:
    settings = get_settings()
    original = settings.MFA_TEST_CODE
    settings.MFA_TEST_CODE = value
    try:
        yield value
    finally:
        settings.MFA_TEST_CODE = original


@pytest.fixture
def mfa_test_code() -> Iterator[str | None]:
    yield from _fixed_code("123456")


@pytest.fixture
def no_mfa_test_code() -> Iterator[str | None]:
    yield from _fixed_code(None)  # whatever a developer's .env says


async def test_a_test_server_accepts_its_fixed_code_again_and_again(client: AsyncClient, super_admin: User, mfa_test_code: str) -> None:
    headers = bearer(await login(client, SUPER_ADMIN_USERNAME, STRONG_PASSWORD))
    setup = await client.post(f"{API}/auth/mfa/setup", json={"password": STRONG_PASSWORD}, headers=headers)
    assert (await client.post(f"{API}/auth/mfa/enable", json={"code": mfa_test_code}, headers=headers)).status_code == 200, setup.text
    for _ in range(2):  # unlike a real code, the fixed one is not used up
        challenge = (await client.post(f"{API}/auth/login", json={"identifier": SUPER_ADMIN_USERNAME, "password": STRONG_PASSWORD})).json()["mfa_challenge"]
        verified = await client.post(f"{API}/auth/mfa/verify", json={"mfa_token": challenge["mfa_token"], "code": mfa_test_code})
        assert verified.status_code == 200, verified.text


@pytest.mark.usefixtures("no_mfa_test_code")
async def test_without_the_setting_the_fixed_code_is_just_a_wrong_code(client: AsyncClient, super_admin: User) -> None:
    headers = bearer(await login(client, SUPER_ADMIN_USERNAME, STRONG_PASSWORD))
    await client.post(f"{API}/auth/mfa/setup", json={"password": STRONG_PASSWORD}, headers=headers)
    assert (await client.post(f"{API}/auth/mfa/enable", json={"code": "123456"}, headers=headers)).status_code == 400


def test_production_refuses_to_start_with_a_fixed_code() -> None:
    from app.core.config import Settings

    with pytest.raises(ValueError, match="MFA_TEST_CODE"):
        Settings(_env_file=None, ENVIRONMENT="production", MFA_TEST_CODE="123456").validate_security()
