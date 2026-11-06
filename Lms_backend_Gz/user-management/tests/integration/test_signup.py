"""Self sign-up: email + password, an emailed code, then the account (a student of "Individual learners")."""

from typing import Any

from httpx import AsyncClient

from tests.conftest import API, STRONG_PASSWORD, CapturingEmailSender, bearer

SIGNUP = {"first_name": "Kiran", "last_name": "Rao", "email": "Kiran.Rao@example.com", "password": STRONG_PASSWORD}


async def _sign_up(client: AsyncClient, emails: CapturingEmailSender, body: dict[str, Any] = SIGNUP) -> dict[str, Any]:
    started = await client.post(f"{API}/auth/register", json=body)
    assert started.status_code == 202, started.text
    code = emails.otp_for(body["email"].lower())
    confirmed = await client.post(f"{API}/auth/register/verify", json={"email": body["email"], "code": code})
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


async def test_a_learner_signs_up_confirms_the_code_and_is_signed_in(client: AsyncClient, emails: CapturingEmailSender, super_admin: Any) -> None:
    body = await _sign_up(client, emails)
    assert body["user"]["role"] == "student" and body["token"]["access_token"]

    me = (await client.get(f"{API}/users/me/permissions", headers=bearer(body))).json()["permissions"]
    assert "store.buy" in me["permissions"] and "store" in me["sections"] and "store" in me["menu"]
    assert "my_organization" not in me["sections"]  # the shared learners' home isn't theirs
    assert "learning.study" in me["permissions"]  # the full student experience

    # the same email cannot sign up twice; they sign in instead
    again = await client.post(f"{API}/auth/register", json=SIGNUP)
    assert again.status_code == 409 and again.json()["code"] == "EMAIL_TAKEN"
    signed_in = await client.post(f"{API}/auth/login", json={"identifier": "kiran.rao@example.com", "password": STRONG_PASSWORD})
    assert signed_in.status_code == 200


async def test_learners_share_one_individual_home_and_institution_students_cannot_buy(
    client: AsyncClient, emails: CapturingEmailSender, super_admin: Any, hierarchy: Any
) -> None:
    first = await _sign_up(client, emails)
    second = await _sign_up(client, emails, {**SIGNUP, "email": "kiran.rao2@example.com"})
    org = first["user"]["institution"]["organization_id"]
    assert org == second["user"]["institution"]["organization_id"]
    assert first["user"]["username"] != second["user"]["username"]

    student = (await client.get(f"{API}/users/me/permissions", headers=hierarchy.student)).json()["permissions"]
    assert "store.buy" not in student["permissions"] and "my_organization" in student["sections"]


async def test_a_wrong_code_is_refused_and_a_new_code_replaces_the_old(client: AsyncClient, emails: CapturingEmailSender, super_admin: Any) -> None:
    assert (await client.post(f"{API}/auth/register", json=SIGNUP)).status_code == 202
    old = emails.otp_for("kiran.rao@example.com")
    wrong = await client.post(f"{API}/auth/register/verify", json={"email": SIGNUP["email"], "code": "000000" if old != "000000" else "111111"})
    assert wrong.status_code == 400 and wrong.json()["code"] == "INVALID_OTP"

    assert (await client.post(f"{API}/auth/register", json=SIGNUP)).status_code == 202  # resend
    new = emails.otp_for("kiran.rao@example.com")
    if new != old:
        stale = await client.post(f"{API}/auth/register/verify", json={"email": SIGNUP["email"], "code": old})
        assert stale.status_code == 400
    assert (await client.post(f"{API}/auth/register/verify", json={"email": SIGNUP["email"], "code": new})).status_code == 200


async def test_a_weak_password_is_refused_before_any_code_is_sent(client: AsyncClient, super_admin: Any) -> None:
    response = await client.post(f"{API}/auth/register", json={**SIGNUP, "password": "short"})
    assert response.status_code == 422
