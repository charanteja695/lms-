"""Role- and person-level permissions: a super admin changes who holds what; the menu and the token follow."""

from typing import Any

import jwt
from httpx import AsyncClient

from app.core.config import get_settings
from tests.conftest import API, NEW_PASSWORD, Hierarchy, bearer, login


async def _me(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    response = await client.get(f"{API}/users/me/permissions", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["permissions"]


def _claims(body: dict[str, Any]) -> set[str]:
    return set(jwt.decode(body["token"]["access_token"], options={"verify_signature": False})["scopes"])


async def test_the_catalog_is_readable_but_only_a_super_admin_changes_anything(
    client: AsyncClient, hierarchy: Hierarchy
) -> None:
    catalog = (await client.get(f"{API}/permissions/catalog", headers=hierarchy.staff)).json()["permissions"]
    grade = next(p for p in catalog if p["key"] == "assessments.grade")
    assert grade["audience"] == "institution" and set(grade["default_roles"]) == {"staff", "institution_head"}
    body = (await client.get(f"{API}/permissions/catalog", headers=hierarchy.staff)).json()
    assert [a["key"] for a in body["actions"]] == ["view", "create", "update", "delete", "revoke", "export", "approve"]
    students = next(p for p in body["pages"] if p["key"] == "students")
    assert students["group"] == "User management" and students["holders"] == ["admin", "institution_head", "staff"]
    delete = next(a for a in students["actions"] if a["action"] == "delete")
    assert delete["key"] == "students.delete" and delete["default_roles"] == ["admin", "institution_head"]
    for headers in (hierarchy.admin, hierarchy.head, hierarchy.staff):
        assert (await client.get(f"{API}/permissions/roles", headers=headers)).status_code == 403
        assert (
            await client.put(
                f"{API}/permissions/roles/staff", json={"changes": {"assessments.grade": False}}, headers=headers
            )
        ).status_code == 403
        assert (await client.get(f"{API}/users/{hierarchy.staff_id}/permissions", headers=headers)).status_code == 403


async def test_a_role_change_applies_to_everyone_in_it_and_can_be_undone(
    client: AsyncClient, hierarchy: Hierarchy
) -> None:
    assert "grading" in (await _me(client, hierarchy.staff))["menu"]
    response = await client.put(
        f"{API}/permissions/roles/staff", json={"changes": {"attempts.view": False}}, headers=hierarchy.root
    )
    assert response.status_code == 200, response.text
    staff_row = next(r for r in response.json()["roles"] if r["role"] == "staff")
    cell = next(c for c in staff_row["permissions"] if c["key"] == "attempts.view")
    assert cell == {"key": "attempts.view", "allowed": False, "changed": True}
    # without View the page's other actions do not count, so the feature key they imply goes too

    me = await _me(client, hierarchy.staff)
    assert "assessments.grade" not in me["permissions"] and "grading" not in me["menu"]
    assert "assessments.grade" not in _claims(await login(client, "staff1", NEW_PASSWORD))
    assert "assessments.grade" in (await _me(client, hierarchy.head))["permissions"]  # other roles untouched

    await client.put(
        f"{API}/permissions/roles/staff", json={"changes": {"attempts.view": None}}, headers=hierarchy.root
    )
    assert "grading" in (await _me(client, hierarchy.staff))["menu"]


async def test_a_person_grant_or_removal_applies_to_them_alone_without_signing_them_out(
    client: AsyncClient, hierarchy: Hierarchy
) -> None:
    before = await login(client, "staff1", NEW_PASSWORD)
    response = await client.put(
        f"{API}/users/{hierarchy.staff_id}/permissions",
        json={
            "changes": {"batches.create": True, "reports.view": False},
            "reason": "Runs batches while the head is away",
        },
        headers=hierarchy.root,
    )
    assert response.status_code == 200, response.text
    cells = {c["key"]: c for c in response.json()["user_permissions"]["permissions"]}
    assert cells["batches.create"] == {"key": "batches.create", "from_role": False, "override": True, "allowed": True}
    assert cells["reports.view"] == {"key": "reports.view", "from_role": True, "override": False, "allowed": False}
    assert cells["reports.export"]["allowed"] is False  # no View, no page

    # the old access token is refused (it carries the old permissions); refreshing keeps them signed in
    assert (await client.get(f"{API}/users/me", headers=bearer(before))).status_code == 401
    refreshed = await client.post(f"{API}/auth/refresh-token", json={"refresh_token": before["token"]["refresh_token"]})
    assert refreshed.status_code == 200, refreshed.text
    claims = _claims(refreshed.json())
    assert {"batches.create", "learning.batches.manage"} <= claims and not {"reports.view", "analytics.own"} & claims
    me = await _me(client, bearer(refreshed.json()))
    assert "analytics" not in me["menu"]

    assert "analytics.own" in (await _me(client, hierarchy.head))["permissions"]  # nobody else changed


async def test_a_removed_cell_stops_that_action(client: AsyncClient, hierarchy: Hierarchy) -> None:
    await client.put(
        f"{API}/users/{hierarchy.staff_id}/permissions",
        json={"changes": {"students.update": False}},
        headers=hierarchy.root,
    )
    staff = bearer(await login(client, "staff1", NEW_PASSWORD))
    me = await _me(client, staff)
    assert "students.update" not in me["permissions"] and "students.view" in me["permissions"]
    response = await client.put(f"{API}/users/{hierarchy.student_id}", json={"address": None}, headers=staff)
    assert response.status_code == 403, response.text
    assert (await client.get(f"{API}/users/{hierarchy.student_id}", headers=staff)).status_code == 200

    await client.put(
        f"{API}/users/{hierarchy.staff_id}/permissions",
        json={"changes": {"students.delete": True}},
        headers=hierarchy.root,
    )
    staff = bearer(await login(client, "staff1", NEW_PASSWORD))
    actions = (await client.get(f"{API}/users/{hierarchy.student_id}", headers=staff)).json()["user"]["allowed_actions"]
    assert actions == ["delete"]


async def test_a_permission_must_suit_the_person(client: AsyncClient, hierarchy: Hierarchy) -> None:
    # platform-only, employer-only, unknown, a head-only cell
    for key in ("billing.manage", "jobs.hire", "no.such.permission", "billing.view", "staff.create"):
        response = await client.put(
            f"{API}/users/{hierarchy.staff_id}/permissions", json={"changes": {key: True}}, headers=hierarchy.root
        )
        assert response.status_code == 422, (key, response.text)
    response = await client.put(
        f"{API}/permissions/roles/student", json={"changes": {"careers.manage": True}}, headers=hierarchy.root
    )
    assert response.status_code == 422


async def test_an_admins_platform_permissions_are_their_scopes(client: AsyncClient, hierarchy: Hierarchy) -> None:
    response = await client.put(
        f"{API}/users/{hierarchy.admin_id}/permissions",
        json={"changes": {"support.manage": True}},
        headers=hierarchy.root,
    )
    assert response.status_code == 200, response.text
    admin = (await client.get(f"{API}/admins/{hierarchy.admin_id}", headers=hierarchy.root)).json()["admin"]
    assert set(admin["scopes"]) == {"accounts.manage", "support.manage"}
    # courses, tests, exams, jobs, billing and AI are the super admin's alone
    refused = await client.put(
        f"{API}/users/{hierarchy.admin_id}/permissions",
        json={"changes": {"careers.manage": True}},
        headers=hierarchy.root,
    )
    assert refused.status_code == 422
    assert "learning.study" not in {
        c["key"] for c in response.json()["user_permissions"]["permissions"]
    }  # members' permissions aren't offered


async def test_a_super_admin_cannot_be_restricted(client: AsyncClient, hierarchy: Hierarchy, super_admin: Any) -> None:
    root_id = str(super_admin.public_id)
    view = (await client.get(f"{API}/users/{root_id}/permissions", headers=hierarchy.root)).json()["user_permissions"]
    assert view["editable"] is False and all(c["allowed"] for c in view["permissions"])
    response = await client.put(
        f"{API}/users/{root_id}/permissions", json={"changes": {"billing.manage": False}}, headers=hierarchy.root
    )
    assert response.status_code == 403


async def test_other_services_ask_who_holds_a_permission_with_the_internal_token(
    client: AsyncClient, hierarchy: Hierarchy, super_admin: Any
) -> None:
    people = [
        hierarchy.head_id,
        hierarchy.staff_id,
        hierarchy.student_id,
        hierarchy.admin_id,
        str(super_admin.public_id),
        "not-an-id",
    ]
    url = f"{API}/internal/permission-holders"
    assert (await client.post(url, json={"permission": "support.agent", "user_ids": people})).status_code == 403
    token = {"X-Internal-Service-Token": get_settings().INTERNAL_SERVICE_TOKEN.get_secret_value()}

    async def holders() -> set[str]:
        response = await client.post(url, json={"permission": "support.agent", "user_ids": people}, headers=token)
        assert response.status_code == 200, response.text
        return set(response.json()["user_ids"])

    assert await holders() == {hierarchy.head_id, hierarchy.staff_id, str(super_admin.public_id)}
    await client.put(
        f"{API}/users/{hierarchy.staff_id}/permissions",
        json={"changes": {"support_queue.view": False}},
        headers=hierarchy.root,
    )
    assert await holders() == {hierarchy.head_id, str(super_admin.public_id)}  # the removal applies at once
