"""Employers (hiring companies) with employer admins and recruiters, and admin scopes."""

import jwt
from httpx import AsyncClient

from tests.conftest import (
    API,
    Hierarchy,
    activate_account,
    admin_payload,
    create_user,
    institution_payload,
    staff_payload,
)


def employer_payload(code: str, **overrides: object) -> dict[str, object]:
    payload = institution_payload(code)
    payload.pop("type")
    payload.update({"name": f"{code} Technologies", "industry": "Information Technology", **overrides})
    return payload


async def _careers_admin(client: AsyncClient, root: dict[str, str]) -> tuple[str, dict[str, str]]:
    body = {**admin_payload("careers.admin"), "scopes": ["careers.manage"]}
    created = await client.post(f"{API}/admins", json=body, headers=root)
    assert created.status_code == 201, created.text
    assert created.json()["admin"]["scopes"] == ["careers.manage"]
    return created.json()["admin"]["user_id"], await activate_account(client, "careers.admin")


async def test_employer_hierarchy_from_admin_to_recruiter(client: AsyncClient, hierarchy: Hierarchy) -> None:
    careers_admin_id, careers_admin = await _careers_admin(client, hierarchy.root)

    # Scopes decide which organisations an admin may own.
    assert (
        await client.post(f"{API}/employers", json=employer_payload("ACME"), headers=hierarchy.admin)
    ).status_code == 403
    assert (
        await client.post(f"{API}/institutions", json=institution_payload("NOPE-01"), headers=careers_admin)
    ).status_code == 403
    created = await client.post(f"{API}/employers", json=employer_payload("ACME"), headers=careers_admin)
    assert created.status_code == 201, created.text
    employer = created.json()["employer"]
    organization_id = employer["organization_id"]
    assert employer["industry"] == "Information Technology"
    assert employer["member_counts"] == {"employer_admins": 0, "recruiters": 0, "total": 0}
    assert employer["allowed_actions"][:2] == ["update", "suspend"]

    # Employers and institutions never mix.
    assert (await client.get(f"{API}/institutions/{organization_id}", headers=hierarchy.root)).status_code == 404
    listed = (await client.get(f"{API}/institutions", headers=hierarchy.root)).json()["institutions"]
    assert organization_id not in {item["organization_id"] for item in listed}
    wrong_type = await client.post(
        f"{API}/users",
        json=staff_payload("wrong.type", role="staff", organization_id=organization_id),
        headers=careers_admin,
    )
    assert wrong_type.status_code in (403, 404, 422)

    lead = await create_user(
        client, careers_admin, staff_payload("hiring.lead", role="employer_admin", organization_id=organization_id)
    )
    assert lead["institution"]["organization_type"] == "employer"
    lead_headers = await activate_account(client, "hiring.lead")
    recruiter = await create_user(client, lead_headers, staff_payload("recruiter.one", role="recruiter"))
    assert recruiter["manager"]["user_id"] == lead["user_id"]

    token = lead_headers["Authorization"].removeprefix("Bearer ")
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["org_type"] == "employer" and claims["scopes"] == []

    permissions = (await client.get(f"{API}/users/me/permissions", headers=lead_headers)).json()["permissions"]
    assert permissions["organization_type"] == "employer"
    assert permissions["users"]["create_roles"] == ["recruiter"]
    assert "my_organization" in permissions["sections"] and "institutions" not in permissions["sections"]
    assert {"job_portal", "ai_interview", "billing"} <= set(permissions["sections"]) and "catalog" not in permissions["sections"]
    assert "assessments" in permissions["sections"]  # hiring tests are the employer's own assessment-service questions/tests
    assert "proctoring" in permissions["sections"]  # employer members monitor and review their own hiring assessments' sessions

    careers_admin_permissions = (await client.get(f"{API}/users/me/permissions", headers=careers_admin)).json()["permissions"]
    assert {"job_portal", "ai_interview", "career", "analytics"} <= set(careers_admin_permissions["sections"])
    # support-service lets only support.manage / exams.manage admins act as agents, so no blanket "support" for admins
    assert "support" not in careers_admin_permissions["sections"]
    assert "billing" not in careers_admin_permissions["sections"] and "catalog" not in careers_admin_permissions["sections"]

    # An employer admin sees only their own recruiters, never institution members.
    visible = (await client.get(f"{API}/users", headers=lead_headers)).json()["users"]
    assert [user["username"] for user in visible] == ["recruiter.one"]
    assert (await client.get(f"{API}/users/{hierarchy.student_id}", headers=lead_headers)).status_code == 404
    # Institution heads cannot create recruiters.
    denied = await client.post(f"{API}/users", json=staff_payload("sneaky", role="recruiter"), headers=hierarchy.head)
    assert denied.status_code == 403

    detail = (await client.get(f"{API}/employers/{organization_id}", headers=careers_admin)).json()["employer"]
    assert detail["member_counts"] == {"employer_admins": 1, "recruiters": 1, "total": 2}
    admin_view = (await client.get(f"{API}/admins/{careers_admin_id}", headers=hierarchy.root)).json()["admin"]
    assert admin_view["employer_count"] == 1 and admin_view["institution_count"] == 0

    # The scope cannot be removed while the admin still owns employers.
    removal = await client.put(
        f"{API}/admins/{careers_admin_id}", json={"scopes": ["content.author"]}, headers=hierarchy.root
    )
    assert removal.status_code == 409 and removal.json()["code"] == "ADMIN_OWNS_ORGANIZATIONS"

    suspended = await client.patch(
        f"{API}/employers/{organization_id}/status", json={"status": "suspended"}, headers=careers_admin
    )
    assert suspended.status_code == 200
    assert (await client.get(f"{API}/users/me", headers=lead_headers)).status_code in (401, 403)


async def test_admin_scopes_are_managed_by_super_admins(client: AsyncClient, hierarchy: Hierarchy) -> None:
    root_permissions = (await client.get(f"{API}/users/me/permissions", headers=hierarchy.root)).json()["permissions"]
    assert "careers.manage" in root_permissions["admin_scopes"] and "employers" in root_permissions["sections"]

    admin = (await client.get(f"{API}/admins/{hierarchy.admin_id}", headers=hierarchy.root)).json()["admin"]
    assert admin["scopes"] == ["accounts.manage"]  # the default

    updated = await client.put(
        f"{API}/admins/{hierarchy.admin_id}",
        json={"scopes": ["accounts.manage", "content.author"]},
        headers=hierarchy.root,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["admin"]["scopes"] == ["accounts.manage", "content.author"]
    # Scopes live in access tokens, so the admin is signed out and gets them at next sign-in.
    assert (await client.get(f"{API}/users/me", headers=hierarchy.admin)).status_code == 401

    by_scope = (await client.get(f"{API}/admins", params={"scope": "content.author"}, headers=hierarchy.root)).json()[
        "admins"
    ]
    assert [item["user_id"] for item in by_scope] == [hierarchy.admin_id]

    invalid = await client.post(
        f"{API}/users", json={**staff_payload("scoped.staff"), "scopes": ["ai.manage"]}, headers=hierarchy.head
    )
    assert invalid.status_code == 422
    unknown = await client.put(
        f"{API}/admins/{hierarchy.admin_id}", json={"scopes": ["root.everything"]}, headers=hierarchy.root
    )
    assert unknown.status_code == 422
