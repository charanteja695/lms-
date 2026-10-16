"""Companies (employers) are run by the super admin with no logins of their own, and admin scopes."""

from httpx import AsyncClient

from tests.conftest import API, Hierarchy, admin_payload, institution_payload, staff_payload

OWNER_ONLY = ("careers.manage", "content.author", "content.review", "exams.manage", "billing.manage", "ai.manage")


def employer_payload(code: str, **overrides: object) -> dict[str, object]:
    payload = institution_payload(code)
    payload.pop("type")
    payload.update({"name": f"{code} Technologies", "industry": "Information Technology", **overrides})
    return payload


async def test_the_super_admin_runs_companies_without_company_logins(client: AsyncClient, hierarchy: Hierarchy) -> None:
    # Admins cannot own companies; the super admin can.
    assert (await client.post(f"{API}/employers", json=employer_payload("ACME"), headers=hierarchy.admin)).status_code == 403
    created = await client.post(f"{API}/employers", json=employer_payload("ACME"), headers=hierarchy.root)
    assert created.status_code == 201, created.text
    employer = created.json()["employer"]
    organization_id = employer["organization_id"]
    assert employer["industry"] == "Information Technology"

    # Employers and institutions never mix.
    assert (await client.get(f"{API}/institutions/{organization_id}", headers=hierarchy.root)).status_code == 404

    # No company logins: nobody can create an employer admin or a recruiter.
    for role in ("employer_admin", "recruiter"):
        body = staff_payload(f"{role}.one", role=role, organization_id=organization_id)
        assert (await client.post(f"{API}/users", json=body, headers=hierarchy.root)).status_code == 403
        assert (await client.post(f"{API}/users", json=body, headers=hierarchy.admin)).status_code == 403

    root_permissions = (await client.get(f"{API}/users/me/permissions", headers=hierarchy.root)).json()["permissions"]
    assert {"employer_admin", "recruiter"}.isdisjoint(root_permissions["users"]["create_roles"])
    assert "employers" in root_permissions["sections"]
    admin_permissions = (await client.get(f"{API}/users/me/permissions", headers=hierarchy.admin)).json()["permissions"]
    assert "employers" not in admin_permissions["sections"]
    assert admin_permissions["users"]["create_roles"] == ["institution_head", "staff", "student"]


async def test_courses_tests_exams_jobs_billing_and_ai_stay_with_the_super_admin(client: AsyncClient, hierarchy: Hierarchy) -> None:
    root_permissions = (await client.get(f"{API}/users/me/permissions", headers=hierarchy.root)).json()["permissions"]
    assert set(OWNER_ONLY) <= set(root_permissions["admin_scopes"])

    admin = (await client.get(f"{API}/admins/{hierarchy.admin_id}", headers=hierarchy.root)).json()["admin"]
    assert admin["scopes"] == ["accounts.manage"]  # the default

    for scope in OWNER_ONLY:
        refused = await client.put(f"{API}/admins/{hierarchy.admin_id}", json={"scopes": ["accounts.manage", scope]}, headers=hierarchy.root)
        assert refused.status_code == 422 and refused.json()["details"][0]["code"] == "SUPER_ADMIN_ONLY", scope
        refused = await client.post(f"{API}/admins", json={**admin_payload("owner.only"), "scopes": [scope]}, headers=hierarchy.root)
        assert refused.status_code == 422, scope

    # What an admin may be given, per the hierarchy: their institutes and people, support and reports.
    updated = await client.put(
        f"{API}/admins/{hierarchy.admin_id}",
        json={"scopes": ["accounts.manage", "analytics.view", "support.manage"]},
        headers=hierarchy.root,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["admin"]["scopes"] == ["accounts.manage", "analytics.view", "support.manage"]
    # Scopes live in access tokens, so the admin is signed out and gets them at next sign-in.
    assert (await client.get(f"{API}/users/me", headers=hierarchy.admin)).status_code == 401

    by_scope = (await client.get(f"{API}/admins", params={"scope": "support.manage"}, headers=hierarchy.root)).json()["admins"]
    assert [item["user_id"] for item in by_scope] == [hierarchy.admin_id]

    form = (await client.get(f"{API}/users/form-options", params={"role": "admin"}, headers=hierarchy.root)).json()
    assert set(form["form_options"]["scopes"]["options"]) == {"accounts.manage", "analytics.view", "support.manage"}

    invalid = await client.post(f"{API}/users", json={**staff_payload("scoped.staff"), "scopes": ["ai.manage"]}, headers=hierarchy.head)
    assert invalid.status_code == 422
    unknown = await client.put(f"{API}/admins/{hierarchy.admin_id}", json={"scopes": ["root.everything"]}, headers=hierarchy.root)
    assert unknown.status_code == 422
