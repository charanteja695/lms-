from httpx import AsyncClient

from tests.conftest import (
    API,
    NEW_PASSWORD,
    CapturingEmailSender,
    Hierarchy,
    activate_account,
    admin_payload,
    bearer,
    create_user,
    institution_payload,
    login,
    staff_payload,
    student_payload,
)


async def test_full_creation_chain(client: AsyncClient, hierarchy: Hierarchy) -> None:
    staff = (await client.get(f"{API}/users/{hierarchy.staff_id}", headers=hierarchy.head)).json()["user"]
    student = (await client.get(f"{API}/users/{hierarchy.student_id}", headers=hierarchy.staff)).json()["user"]

    assert staff["institution"]["organization_id"] == hierarchy.organization_id
    assert staff["manager"]["user_id"] == hierarchy.head_id  # defaults to the creator
    assert staff["employment"]["employee_code"] == "EMP-STAFF1"
    assert student["manager"]["user_id"] == hierarchy.staff_id
    assert student["created_by"]["user_id"] == hierarchy.staff_id
    assert student["student"]["admission_number"] == "ADM/STUDENT1"
    assert student["student"]["guardians"][0]["is_primary"] is True
    assert student["personal_info"]["timezone"] == "Asia/Kolkata"
    assert student["employment"] is None


async def test_institution_counts_and_admin_view(client: AsyncClient, hierarchy: Hierarchy) -> None:
    institution = (await client.get(f"{API}/institutions/{hierarchy.organization_id}", headers=hierarchy.admin)).json()[
        "institution"
    ]
    assert institution["member_counts"] == {"institution_heads": 1, "staff": 1, "students": 1, "total": 3}
    assert institution["admin"]["user_id"] == hierarchy.admin_id

    admin = (await client.get(f"{API}/admins/{hierarchy.admin_id}", headers=hierarchy.root)).json()["admin"]
    assert admin["institution_count"] == 1
    admins = (await client.get(f"{API}/admins", headers=hierarchy.root)).json()
    assert admins["page_context"]["total_records"] == 1


async def test_temporary_password_blocks_everything_until_changed(client: AsyncClient, hierarchy: Hierarchy) -> None:
    await create_user(client, hierarchy.head, staff_payload("newstaff"))
    headers = bearer(await login(client, "newstaff"))
    assert (await client.get(f"{API}/users/me", headers=headers)).status_code == 200
    blocked = await client.get(f"{API}/users", headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "PASSWORD_CHANGE_REQUIRED"


async def test_users_cannot_create_outside_their_level(client: AsyncClient, hierarchy: Hierarchy) -> None:
    cases = [
        (hierarchy.admin, {**admin_payload("admin9"), "role": "admin"}),
        (hierarchy.head, staff_payload("head9", role="institution_head")),
        (hierarchy.staff, staff_payload("staff9")),
        (hierarchy.student, student_payload("student9")),
    ]
    for headers, payload in cases:
        response = await client.post(f"{API}/users", json=payload, headers=headers)
        assert response.status_code == 403, (payload["role"], response.text)

    super_admin_attempt = await client.post(
        f"{API}/users", json=staff_payload("root9", role="super_admin"), headers=hierarchy.root
    )
    assert super_admin_attempt.status_code == 422
    assert super_admin_attempt.json()["details"][0]["field"] == "role"


async def test_non_super_admins_cannot_use_admin_endpoints(client: AsyncClient, hierarchy: Hierarchy) -> None:
    for headers in (hierarchy.admin, hierarchy.head, hierarchy.student):
        assert (await client.get(f"{API}/admins", headers=headers)).status_code == 403


async def test_institution_isolation(client: AsyncClient, hierarchy: Hierarchy) -> None:
    await client.post(f"{API}/admins", json=admin_payload("admin2"), headers=hierarchy.root)
    admin2 = await activate_account(client, "admin2")
    other = (await client.post(f"{API}/institutions", json=institution_payload("SHV"), headers=admin2)).json()[
        "institution"
    ]
    other_head = await create_user(
        client, admin2, staff_payload("head2", role="institution_head", organization_id=other["organization_id"])
    )

    # Admin 1 cannot see or touch admin 2's institution or users (reported as not found).
    assert (
        await client.get(f"{API}/institutions/{other['organization_id']}", headers=hierarchy.admin)
    ).status_code == 404
    assert (await client.get(f"{API}/users/{other_head['user_id']}", headers=hierarchy.admin)).status_code == 404
    assert (await client.delete(f"{API}/users/{other_head['user_id']}", headers=hierarchy.head)).status_code == 404
    denied = await client.post(
        f"{API}/users",
        json=staff_payload("sneaky", organization_id=other["organization_id"]),
        headers=hierarchy.head,
    )
    assert denied.status_code == 403

    listed = (await client.get(f"{API}/institutions", headers=hierarchy.admin)).json()
    assert [i["organization_id"] for i in listed["institutions"]] == [hierarchy.organization_id]
    admin_users = (await client.get(f"{API}/users", headers=hierarchy.admin)).json()
    assert other_head["user_id"] not in {u["user_id"] for u in admin_users["users"]}
    assert admin_users["page_context"]["total_records"] == 3  # head, staff, student

    # The same employee code is fine in a different institution.
    await create_user(
        client,
        admin2,
        staff_payload(
            "staff.other", organization_id=other["organization_id"], employment={"employee_code": "EMP-STAFF1"}
        ),
    )


async def test_list_filters_search_and_sort(client: AsyncClient, hierarchy: Hierarchy) -> None:
    head_view = (await client.get(f"{API}/users", headers=hierarchy.head)).json()
    assert {u["role"] for u in head_view["users"]} == {"staff", "student"}
    staff_view = (await client.get(f"{API}/users", headers=hierarchy.staff)).json()
    assert {u["role"] for u in staff_view["users"]} == {"student"}
    assert (await client.get(f"{API}/users", headers=hierarchy.student)).status_code == 403

    by_code = (await client.get(f"{API}/users", params={"search_text": "adm/student"}, headers=hierarchy.head)).json()
    assert [u["user_id"] for u in by_code["users"]] == [hierarchy.student_id]
    by_manager = (
        await client.get(f"{API}/users", params={"manager_user_id": hierarchy.head_id}, headers=hierarchy.admin)
    ).json()
    assert [u["user_id"] for u in by_manager["users"]] == [hierarchy.staff_id]

    page = (
        await client.get(
            f"{API}/users",
            params={"per_page": 1, "sort_column": "first_name", "sort_order": "asc"},
            headers=hierarchy.admin,
        )
    ).json()
    assert page["users"][0]["full_name"].startswith("Head")
    assert page["page_context"] == {
        "page": 1,
        "per_page": 1,
        "total_records": 3,
        "total_is_exact": True,
        "total_pages": 3,
        "has_more_page": True,
        "sort_column": "first_name",
        "sort_order": "asc",
    }


async def test_staff_cannot_suspend_delete_or_revoke(client: AsyncClient, hierarchy: Hierarchy) -> None:
    url = f"{API}/users/{hierarchy.student_id}"
    assert (
        await client.patch(f"{url}/status", json={"status": "suspended"}, headers=hierarchy.staff)
    ).status_code == 403
    assert (await client.delete(url, headers=hierarchy.staff)).status_code == 403
    assert (await client.post(f"{url}/revoke", headers=hierarchy.staff)).status_code == 403
    renamed = await client.put(url, json={"personal_info": {"first_name": "Renamed"}}, headers=hierarchy.staff)
    assert renamed.status_code == 200
    assert renamed.json()["user"]["personal_info"]["full_name"] == "Renamed Test"


async def test_cannot_act_on_own_account(client: AsyncClient, hierarchy: Hierarchy) -> None:
    response = await client.patch(
        f"{API}/users/{hierarchy.head_id}/status", json={"status": "suspended"}, headers=hierarchy.head
    )
    assert response.status_code == 403
    assert response.json()["code"] == "SELF_ACTION_NOT_ALLOWED"


async def test_suspend_blocks_login_and_existing_tokens(client: AsyncClient, hierarchy: Hierarchy) -> None:
    response = await client.patch(
        f"{API}/users/{hierarchy.staff_id}/status",
        json={"status": "suspended", "reason": "Investigation pending"},
        headers=hierarchy.head,
    )
    assert response.status_code == 200
    assert response.json()["user"]["status"] == "suspended"
    assert response.json()["user"]["status_reason"] == "Investigation pending"
    assert (await client.get(f"{API}/users/me", headers=hierarchy.staff)).status_code == 401
    denied = await client.post(f"{API}/auth/login", json={"identifier": "staff1", "password": NEW_PASSWORD})
    assert denied.status_code == 403
    assert denied.json()["code"] == "ACCOUNT_INACTIVE"

    await client.patch(f"{API}/users/{hierarchy.staff_id}/status", json={"status": "active"}, headers=hierarchy.head)
    await login(client, "staff1", NEW_PASSWORD)


async def test_revoke_ends_sessions_but_allows_new_login(client: AsyncClient, hierarchy: Hierarchy) -> None:
    response = await client.post(f"{API}/users/{hierarchy.student_id}/revoke", headers=hierarchy.head)
    assert response.status_code == 200
    assert (await client.get(f"{API}/users/me", headers=hierarchy.student)).status_code == 401
    await login(client, "student1", NEW_PASSWORD)


async def test_delete_hides_user_and_frees_identity(client: AsyncClient, hierarchy: Hierarchy) -> None:
    assert (await client.delete(f"{API}/users/{hierarchy.student_id}", headers=hierarchy.head)).status_code == 200
    assert (await client.get(f"{API}/users/{hierarchy.student_id}", headers=hierarchy.head)).status_code == 404
    assert (await client.get(f"{API}/users/me", headers=hierarchy.student)).status_code == 401
    login_attempt = await client.post(f"{API}/auth/login", json={"identifier": "student1", "password": NEW_PASSWORD})
    assert login_attempt.status_code == 401

    deleted = (await client.get(f"{API}/users/{hierarchy.student_id}", headers=hierarchy.root)).json()["user"]
    assert deleted["status"] == "deleted"
    assert deleted["deleted_time"] is not None

    # Email and username can be reused; the admission number cannot.
    reused = await client.post(f"{API}/users", json=student_payload("student1"), headers=hierarchy.head)
    assert reused.status_code == 409
    assert reused.json()["details"][0]["code"] == "DUPLICATE_ADMISSION_NUMBER"
    fresh = student_payload("student1")
    fresh["student"]["admission_number"] = "ADM/NEW-001"
    await create_user(client, hierarchy.head, fresh)


async def test_admin_with_institutions_cannot_be_deleted(client: AsyncClient, hierarchy: Hierarchy) -> None:
    response = await client.delete(f"{API}/admins/{hierarchy.admin_id}", headers=hierarchy.root)
    assert response.status_code == 409
    assert response.json()["code"] == "ADMIN_HAS_INSTITUTIONS"


async def test_suspending_institution_blocks_all_members(client: AsyncClient, hierarchy: Hierarchy) -> None:
    response = await client.patch(
        f"{API}/institutions/{hierarchy.organization_id}/status", json={"status": "suspended"}, headers=hierarchy.admin
    )
    assert response.status_code == 200
    for headers in (hierarchy.head, hierarchy.staff, hierarchy.student):
        assert (await client.get(f"{API}/users/me", headers=headers)).status_code == 401
    denied = await client.post(f"{API}/auth/login", json={"identifier": "head1", "password": NEW_PASSWORD})
    assert denied.json()["code"] == "INSTITUTION_INACTIVE"
    assert (await client.get(f"{API}/users/me", headers=hierarchy.admin)).status_code == 200


async def test_institution_revoke_signs_out_members(client: AsyncClient, hierarchy: Hierarchy) -> None:
    response = await client.post(f"{API}/institutions/{hierarchy.organization_id}/revoke", headers=hierarchy.admin)
    assert response.status_code == 200
    assert (await client.get(f"{API}/users/me", headers=hierarchy.staff)).status_code == 401
    await login(client, "staff1", NEW_PASSWORD)


async def test_only_owner_admin_or_super_admin_manage_institution(client: AsyncClient, hierarchy: Hierarchy) -> None:
    url = f"{API}/institutions/{hierarchy.organization_id}"
    assert (await client.get(url, headers=hierarchy.student)).status_code == 200
    assert (await client.put(url, json={"name": "Nope School"}, headers=hierarchy.head)).status_code == 403
    transfer = await client.put(url, json={"admin_user_id": hierarchy.head_id}, headers=hierarchy.admin)
    assert transfer.status_code == 403
    updated = await client.put(
        url,
        json={"name": "Springfield Senior High", "contact": {"website": "https://sph.example.edu"}},
        headers=hierarchy.admin,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["institution"]["name"] == "Springfield Senior High"
    assert updated.json()["institution"]["contact"]["website"] == "https://sph.example.edu"


async def test_duplicate_identity_and_code_conflicts(client: AsyncClient, hierarchy: Hierarchy) -> None:
    payload = staff_payload("other.staff")
    payload["account"]["username"] = "STAFF1"
    payload["employment"]["employee_code"] = "emp-staff1"
    dup = await client.post(f"{API}/users", json=payload, headers=hierarchy.head)
    assert dup.status_code == 409
    assert {d["code"] for d in dup.json()["details"]} == {"DUPLICATE_USERNAME", "DUPLICATE_EMPLOYEE_CODE"}

    code = await client.post(f"{API}/institutions", json=institution_payload("sph-01"), headers=hierarchy.admin)
    assert code.status_code == 409
    assert code.json()["details"][0]["code"] == "DUPLICATE_CODE"


async def test_role_change_rules(client: AsyncClient, hierarchy: Hierarchy) -> None:
    to_head = await client.put(
        f"{API}/users/{hierarchy.staff_id}", json={"role": "institution_head"}, headers=hierarchy.head
    )
    assert to_head.status_code == 403  # heads cannot create other heads
    student_to_staff = await client.put(
        f"{API}/users/{hierarchy.student_id}", json={"role": "staff"}, headers=hierarchy.admin
    )
    assert student_to_staff.status_code == 422
    assert student_to_staff.json()["code"] == "ROLE_CHANGE_NOT_ALLOWED"

    promoted = await client.put(
        f"{API}/users/{hierarchy.staff_id}", json={"role": "institution_head"}, headers=hierarchy.admin
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["user"]["manager"] is None
    assert (await client.get(f"{API}/users/me", headers=hierarchy.staff)).status_code == 401


async def test_update_sections_and_guardians(client: AsyncClient, hierarchy: Hierarchy) -> None:
    response = await client.put(
        f"{API}/users/{hierarchy.student_id}",
        json={
            "address": {
                "line1": "12 MG Road",
                "city": "Bengaluru",
                "state": "Karnataka",
                "postal_code": "560001",
                "country": "in",
            },
            "student": {
                "guardians": [
                    {
                        "full_name": "Suresh Test",
                        "relationship": "father",
                        "phone": "+919876543210",
                        "is_primary": True,
                    },
                    {"full_name": "Kavya Test", "relationship": "mother", "phone": "9876500000"},
                ]
            },
        },
        headers=hierarchy.staff,
    )
    assert response.status_code == 200, response.text
    user = response.json()["user"]
    assert user["address"]["country"] == "IN"
    assert [g["phone"] for g in user["student"]["guardians"]] == ["+919876543210", "+919876500000"]

    cleared = await client.put(f"{API}/users/{hierarchy.student_id}", json={"address": None}, headers=hierarchy.staff)
    assert cleared.json()["user"]["address"] is None


async def test_self_service_profile(client: AsyncClient, hierarchy: Hierarchy) -> None:
    ok = await client.put(
        f"{API}/users/me",
        json={"personal_info": {"alternate_phone": "+919000011111", "preferred_language": "te"}},
        headers=hierarchy.student,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["user"]["personal_info"]["preferred_language"] == "te"

    name_change = await client.put(
        f"{API}/users/me", json={"personal_info": {"first_name": "Hacker"}}, headers=hierarchy.student
    )
    assert name_change.status_code == 422
    assert name_change.json()["details"][0]["code"] == "UNKNOWN_FIELD"

    clear_staff_phone = await client.put(
        f"{API}/users/me", json={"personal_info": {"phone": None}}, headers=hierarchy.staff
    )
    assert clear_staff_phone.status_code == 422
    assert clear_staff_phone.json()["details"][0]["field"] == "personal_info.phone"


async def test_account_setup_link_flow(client: AsyncClient, hierarchy: Hierarchy, emails: CapturingEmailSender) -> None:
    payload = student_payload("invitee")
    del payload["account"]["password"]
    del payload["account"]["username"]
    payload["personal_info"]["first_name"] = "Aarav"
    payload["personal_info"]["last_name"] = "Reddy"
    created = await create_user(client, hierarchy.staff, payload)
    assert created["account"]["username"] == "aarav.reddy"
    assert created["account"]["email_verified"] is False

    token = emails.link_token_for("invitee@example.com")
    setup = await client.post(
        f"{API}/auth/reset-password",
        json={"reset_token": token, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
    )
    assert setup.status_code == 200, setup.text
    body = await login(client, "aarav.reddy", NEW_PASSWORD)
    assert body["user"]["must_change_password"] is False
    me = (await client.get(f"{API}/users/me", headers=bearer(body))).json()["user"]
    assert me["account"]["email_verified"] is True
