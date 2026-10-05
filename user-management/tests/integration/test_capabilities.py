"""Clients render from server-computed permissions: my permissions, allowed actions and user form options."""

from httpx import AsyncClient

from tests.conftest import API, Hierarchy


async def test_my_permissions_follow_the_hierarchy(client: AsyncClient, hierarchy: Hierarchy) -> None:
    root = (await client.get(f"{API}/users/me/permissions", headers=hierarchy.root)).json()["permissions"]
    assert root["sections"][:3] == ["dashboard", "admins", "institutions"]
    assert root["users"]["filter_statuses"] == ["active", "suspended", "deleted"]
    assert root["admins"] == {"view": True, "create": True}

    head = (await client.get(f"{API}/users/me/permissions", headers=hierarchy.head)).json()["permissions"]
    assert "admins" not in head["sections"] and "institutions" not in head["sections"]
    assert {"my_organization", "users", "audit_logs"} <= set(head["sections"])
    assert head["users"]["create_roles"] == ["staff", "student"]
    assert head["users"]["filter_by_institution"] is False
    assert head["institutions"]["create"] is False

    staff = (await client.get(f"{API}/users/me/permissions", headers=hierarchy.staff)).json()["permissions"]
    assert staff["users"]["view_roles"] == ["student"] and staff["users"]["create_roles"] == ["student"]
    assert "audit_logs" not in staff["sections"]
    assert {"catalog", "learning", "analytics", "proctoring"} <= set(staff["sections"]) and "subscriptions" not in staff["sections"]
    assert "subscriptions" in head["sections"] and "billing" in head["sections"]  # the head requests courses and sees institution billing; staff do neither

    # An admin with the default accounts.manage scope approves course requests and manages
    # batches across every institution (subscription-service and learning-service).
    admin = (await client.get(f"{API}/users/me/permissions", headers=hierarchy.admin)).json()["permissions"]
    assert admin["scopes"] == ["accounts.manage"]
    assert {"subscriptions", "learning"} <= set(admin["sections"])

    student = (await client.get(f"{API}/users/me/permissions", headers=hierarchy.student)).json()["permissions"]
    assert student["sections"] == [
        "dashboard", "my_organization", "catalog", "learning", "code_execution", "assessments", "proctoring", "certificates", "ai_tutor", "support", "career", "job_portal", "ai_interview", "notifications",
        "profile", "security",
    ]
    assert "billing" not in student["sections"] and "analytics" not in student["sections"] and "subscriptions" not in student["sections"]


async def test_records_carry_the_actions_the_viewer_may_take(client: AsyncClient, hierarchy: Hierarchy) -> None:
    as_head = (await client.get(f"{API}/users/{hierarchy.staff_id}", headers=hierarchy.head)).json()["user"]
    assert as_head["allowed_actions"] == ["update", "suspend", "revoke_sessions", "reset_mfa", "set_password", "delete"]

    as_staff = (await client.get(f"{API}/users", headers=hierarchy.staff)).json()["users"]
    assert as_staff[0]["user_id"] == hierarchy.student_id
    assert as_staff[0]["allowed_actions"] == ["update", "set_password"]

    me = (await client.get(f"{API}/users/me", headers=hierarchy.head)).json()["user"]
    assert me["allowed_actions"] == []

    institution = f"{API}/institutions/{hierarchy.organization_id}"
    owner_view = (await client.get(institution, headers=hierarchy.admin)).json()["institution"]
    assert owner_view["allowed_actions"] == [
        "update",
        "suspend",
        "revoke_sessions",
        "delete",
        "add_member",
        "view_members",
    ]
    staff_view = (await client.get(institution, headers=hierarchy.staff)).json()["institution"]
    assert staff_view["allowed_actions"] == ["add_member", "view_members"]
    student_view = (await client.get(institution, headers=hierarchy.student)).json()["institution"]
    assert student_view["allowed_actions"] == []


async def test_user_form_options_describe_the_form_for_each_role(client: AsyncClient, hierarchy: Hierarchy) -> None:
    url = f"{API}/users/form-options"
    student = (await client.get(url, params={"role": "student"}, headers=hierarchy.head)).json()["form_options"]
    assert student["roles"] == ["staff", "student"]
    assert student["organization"] == {
        "shown": True,
        "type": "institution",
        "required": True,
        "selectable": False,
        "fixed": True,
    }
    assert student["manager"]["role"] == "staff" and student["manager"]["defaults_to_you"] is False
    assert student["sections"] == {"address": True, "employment": False, "student": True, "guardians": True}
    assert student["email_optional"] is True and student["initial_password"]["generated_without_email"] is True
    assert {"personal_info.date_of_birth", "student.admission_number"} <= set(student["required_fields"])
    assert "account.email" not in student["required_fields"]

    staff = (await client.get(url, params={"role": "staff"}, headers=hierarchy.head)).json()["form_options"]
    assert staff["manager"] == {"shown": True, "role": "institution_head", "defaults_to_you": True}
    assert {"account.email", "personal_info.phone", "employment.employee_code"} <= set(staff["required_fields"])

    admin = (await client.get(url, params={"role": "admin"}, headers=hierarchy.root)).json()["form_options"]
    assert admin["organization"]["shown"] is False and admin["sections"]["employment"] is True
    assert "employment.employee_code" not in admin["required_fields"]

    # Editing: a head may not promote staff, an admin may switch head <-> staff; students keep their role.
    edit = {"user_id": hierarchy.staff_id}
    assert (await client.get(url, params=edit, headers=hierarchy.head)).json()["form_options"]["roles"] == ["staff"]
    assert (await client.get(url, params=edit, headers=hierarchy.admin)).json()["form_options"]["roles"] == [
        "institution_head",
        "staff",
    ]
    student_edit = (await client.get(url, params={"user_id": hierarchy.student_id}, headers=hierarchy.staff)).json()
    assert (
        student_edit["form_options"]["roles"] == ["student"]
        and student_edit["form_options"]["initial_password"]["allowed"] is False
    )

    hidden = await client.get(url, params={"user_id": hierarchy.head_id}, headers=hierarchy.staff)
    assert hidden.status_code == 404
