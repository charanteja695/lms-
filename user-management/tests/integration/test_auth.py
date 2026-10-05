from httpx import AsyncClient

from app.models import User
from tests.conftest import (
    API,
    NEW_PASSWORD,
    STRONG_PASSWORD,
    SUPER_ADMIN_EMAIL,
    SUPER_ADMIN_USERNAME,
    CapturingEmailSender,
    bearer,
    login,
)


def _reset_body(token: str, password: str = NEW_PASSWORD) -> dict[str, str]:
    return {"reset_token": token, "new_password": password, "confirm_password": password}


async def test_login_with_email_or_username(client: AsyncClient, super_admin: User) -> None:
    by_email = await login(client, SUPER_ADMIN_EMAIL.upper())
    by_username = await login(client, SUPER_ADMIN_USERNAME.upper())
    for body in (by_email, by_username):
        assert body["status"] == "success"
        assert body["code"] == "SUCCESS"
        assert body["token"]["token_type"] == "Bearer"
        assert body["user"]["user_id"] == str(super_admin.public_id)
        assert body["user"]["role"] == "super_admin"
        assert set(body["user"]) == {
            "user_id", "full_name", "email", "username", "role", "institution", "scopes", "must_change_password", "mfa_enabled", "mfa_setup_required",
        }  # fmt: skip


async def test_login_errors_do_not_reveal_whether_account_exists(client: AsyncClient, super_admin: User) -> None:
    wrong_password = await client.post(
        f"{API}/auth/login", json={"identifier": SUPER_ADMIN_USERNAME, "password": "nope"}
    )
    unknown_user = await client.post(f"{API}/auth/login", json={"identifier": "ghost", "password": "nope"})
    assert wrong_password.status_code == unknown_user.status_code == 401
    for response in (wrong_password, unknown_user):
        body = response.json()
        assert body["status"] == "error"
        assert body["code"] == "INVALID_CREDENTIALS"
    assert wrong_password.json()["message"] == unknown_user.json()["message"]


async def test_account_locks_after_repeated_failures(client: AsyncClient, super_admin: User) -> None:
    for _ in range(5):
        await client.post(f"{API}/auth/login", json={"identifier": SUPER_ADMIN_USERNAME, "password": "wrong-password"})
    response = await client.post(
        f"{API}/auth/login", json={"identifier": SUPER_ADMIN_USERNAME, "password": STRONG_PASSWORD}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "ACCOUNT_LOCKED"
    assert int(response.headers["Retry-After"]) > 0


async def test_protected_endpoint_requires_valid_token(client: AsyncClient, super_admin: User) -> None:
    missing = await client.get(f"{API}/users/me")
    assert missing.status_code == 401
    assert missing.json()["code"] == "NOT_AUTHENTICATED"
    response = await client.get(f"{API}/users/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


async def test_refresh_rotates_and_detects_reuse(client: AsyncClient, super_admin: User) -> None:
    body = await login(client, SUPER_ADMIN_USERNAME)
    old_refresh = body["token"]["refresh_token"]
    rotated = await client.post(f"{API}/auth/refresh-token", json={"refresh_token": old_refresh})
    assert rotated.status_code == 200
    new_body = rotated.json()
    assert new_body["token"]["refresh_token"] != old_refresh

    # Replaying the old refresh token is treated as theft: the session ends.
    replay = await client.post(f"{API}/auth/refresh-token", json={"refresh_token": old_refresh})
    assert replay.status_code == 401
    after = await client.post(f"{API}/auth/refresh-token", json={"refresh_token": new_body["token"]["refresh_token"]})
    assert after.status_code == 401
    assert (await client.get(f"{API}/users/me", headers=bearer(new_body))).status_code == 401


async def test_logout_and_device_sessions(client: AsyncClient, super_admin: User) -> None:
    laptop = await login(client, SUPER_ADMIN_USERNAME)
    phone = await login(client, SUPER_ADMIN_USERNAME)

    sessions = (await client.get(f"{API}/auth/sessions", headers=bearer(laptop))).json()["sessions"]
    assert len(sessions) == 2
    assert sum(s["is_current"] for s in sessions) == 1

    other = next(s for s in sessions if not s["is_current"])
    ended = await client.delete(f"{API}/auth/sessions/{other['session_id']}", headers=bearer(laptop))
    assert ended.status_code == 200
    assert (await client.get(f"{API}/users/me", headers=bearer(phone))).status_code == 401

    assert (await client.post(f"{API}/auth/logout", headers=bearer(laptop))).status_code == 200
    assert (await client.get(f"{API}/users/me", headers=bearer(laptop))).status_code == 401


async def test_logout_all_sessions(client: AsyncClient, super_admin: User) -> None:
    first = await login(client, SUPER_ADMIN_USERNAME)
    second = await login(client, SUPER_ADMIN_USERNAME)
    response = await client.post(f"{API}/auth/logout", json={"all_sessions": True}, headers=bearer(first))
    assert response.json()["message"] == "Logged out of all devices."
    assert (await client.get(f"{API}/users/me", headers=bearer(second))).status_code == 401


async def test_forgot_password_with_otp(client: AsyncClient, super_admin: User, emails: CapturingEmailSender) -> None:
    old_session = await login(client, SUPER_ADMIN_USERNAME)

    response = await client.post(f"{API}/auth/forgot-password", json={"identifier": SUPER_ADMIN_USERNAME})
    assert response.status_code == 202
    otp = emails.otp_for(SUPER_ADMIN_EMAIL)

    wrong = "000000" if otp != "000000" else "111111"
    bad = await client.post(f"{API}/auth/verify-otp", json={"identifier": SUPER_ADMIN_USERNAME, "otp": wrong})
    assert bad.status_code == 400
    assert bad.json()["code"] == "INVALID_OTP"

    verified = await client.post(f"{API}/auth/verify-otp", json={"identifier": SUPER_ADMIN_USERNAME, "otp": otp})
    assert verified.status_code == 200, verified.text
    reset_token = verified.json()["password_reset"]["reset_token"]

    mismatch = await client.post(
        f"{API}/auth/reset-password",
        json={"reset_token": reset_token, "new_password": NEW_PASSWORD, "confirm_password": "different"},
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["details"][0] == {
        "field": "confirm_password",
        "code": "PASSWORD_MISMATCH",
        "message": "Passwords do not match",
    }

    weak = await client.post(f"{API}/auth/reset-password", json=_reset_body(reset_token, "short"))
    assert weak.status_code == 422
    assert weak.json()["code"] == "WEAK_PASSWORD"

    reset = await client.post(f"{API}/auth/reset-password", json=_reset_body(reset_token))
    assert reset.status_code == 200, reset.text

    # Single use, old sessions are gone, old password no longer works.
    again = await client.post(f"{API}/auth/reset-password", json=_reset_body(reset_token))
    assert again.status_code == 400
    assert (await client.get(f"{API}/users/me", headers=bearer(old_session))).status_code == 401
    old_password = await client.post(
        f"{API}/auth/login", json={"identifier": SUPER_ADMIN_USERNAME, "password": STRONG_PASSWORD}
    )
    assert old_password.status_code == 401
    await login(client, SUPER_ADMIN_USERNAME, NEW_PASSWORD)


async def test_forgot_password_with_email_link(
    client: AsyncClient, super_admin: User, emails: CapturingEmailSender
) -> None:
    await client.post(f"{API}/auth/forgot-password", json={"identifier": SUPER_ADMIN_EMAIL})
    link_token = emails.link_token_for(SUPER_ADMIN_EMAIL)
    reset = await client.post(f"{API}/auth/reset-password", json=_reset_body(link_token))
    assert reset.status_code == 200, reset.text
    await login(client, SUPER_ADMIN_USERNAME, NEW_PASSWORD)


async def test_forgot_password_is_silent_for_unknown_accounts(
    client: AsyncClient, emails: CapturingEmailSender
) -> None:
    response = await client.post(f"{API}/auth/forgot-password", json={"identifier": "nobody@example.com"})
    assert response.status_code == 202
    assert emails.messages == []


async def test_otp_is_burned_after_max_attempts(
    client: AsyncClient, super_admin: User, emails: CapturingEmailSender
) -> None:
    await client.post(f"{API}/auth/forgot-password", json={"identifier": SUPER_ADMIN_USERNAME})
    otp = emails.otp_for(SUPER_ADMIN_EMAIL)
    wrong = "000000" if otp != "000000" else "111111"
    for _ in range(5):
        await client.post(f"{API}/auth/verify-otp", json={"identifier": SUPER_ADMIN_USERNAME, "otp": wrong})
    response = await client.post(f"{API}/auth/verify-otp", json={"identifier": SUPER_ADMIN_USERNAME, "otp": otp})
    assert response.status_code == 400


async def test_change_password_rules(client: AsyncClient, super_admin: User) -> None:
    headers = bearer(await login(client, SUPER_ADMIN_USERNAME))

    def body(current: str, new: str) -> dict[str, str]:
        return {"current_password": current, "new_password": new, "confirm_password": new}

    wrong_current = await client.post(f"{API}/auth/change-password", json=body("wrong", NEW_PASSWORD), headers=headers)
    assert wrong_current.status_code == 400
    assert wrong_current.json()["code"] == "INVALID_CURRENT_PASSWORD"

    reused = await client.post(
        f"{API}/auth/change-password", json=body(STRONG_PASSWORD, STRONG_PASSWORD), headers=headers
    )
    assert reused.status_code == 422
    assert reused.json()["code"] == "PASSWORD_REUSED"

    ok = await client.post(f"{API}/auth/change-password", json=body(STRONG_PASSWORD, NEW_PASSWORD), headers=headers)
    assert ok.status_code == 200
    assert (await client.get(f"{API}/users/me", headers=headers)).status_code == 401


async def test_login_rate_limit(client: AsyncClient, super_admin: User) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    original = settings.LOGIN_RATE_LIMIT_PER_MINUTE
    settings.LOGIN_RATE_LIMIT_PER_MINUTE = 2
    try:
        responses = [
            await client.post(f"{API}/auth/login", json={"identifier": "ghost", "password": "x"}) for _ in range(3)
        ]
    finally:
        settings.LOGIN_RATE_LIMIT_PER_MINUTE = original
    assert responses[-1].status_code == 429
    assert responses[-1].json()["code"] == "TOO_MANY_REQUESTS"


async def test_security_headers_and_request_id(client: AsyncClient) -> None:
    response = await client.get("/health/live", headers={"X-Request-ID": "trace-12345678"})
    assert response.headers["X-Request-ID"] == "trace-12345678"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
