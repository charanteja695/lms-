"""Student academic profile, students without email, manager-set passwords and the audit log API."""

from httpx import AsyncClient

from tests.conftest import API, NEW_PASSWORD, Hierarchy, institution_payload, login, student_payload

ACADEMIC = {
    "program": "B.Tech",
    "branch": "Computer Science",
    "year_of_study": 3,
    "section": "A",
    "graduation_year": 2027,
    "cgpa": "8.45",
}


async def test_academic_profile_is_stored_filtered_and_updated(client: AsyncClient, hierarchy: Hierarchy) -> None:
    payload = student_payload("riya.cs")
    payload["student"] = {**payload["student"], **ACADEMIC}
    created = await client.post(f"{API}/users", json=payload, headers=hierarchy.staff)
    assert created.status_code == 201, created.text
    student = created.json()["user"]["student"]
    assert {key: student[key] for key in ACADEMIC} == ACADEMIC

    listed = await client.get(
        f"{API}/users", params={"branch": "computer science", "graduation_year": 2027}, headers=hierarchy.head
    )
    rows = listed.json()["users"]
    assert [row["username"] for row in rows] == ["riya.cs"]
    assert rows[0]["year_of_study"] == 3 and rows[0]["section"] == "A"
    assert (await client.get(f"{API}/users", params={"graduation_year": 2030}, headers=hierarchy.head)).json()[
        "users"
    ] == []

    user_id = created.json()["user"]["user_id"]
    updated = await client.put(
        f"{API}/users/{user_id}", json={"student": {"year_of_study": 4, "cgpa": None}}, headers=hierarchy.staff
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["user"]["student"]["year_of_study"] == 4
    assert updated.json()["user"]["student"]["cgpa"] is None
    assert updated.json()["user"]["student"]["branch"] == "Computer Science"

    invalid = await client.put(
        f"{API}/users/{user_id}", json={"student": {"year_of_study": 0, "cgpa": "11"}}, headers=hierarchy.staff
    )
    assert invalid.status_code == 422
    assert {d["field"] for d in invalid.json()["details"]} == {"student.year_of_study", "student.cgpa"}


async def test_student_without_email_gets_a_one_time_temporary_password(
    client: AsyncClient, hierarchy: Hierarchy
) -> None:
    payload = student_payload("no.email.kid")
    payload["account"] = {"username": "no.email.kid"}
    created = await client.post(f"{API}/users", json=payload, headers=hierarchy.staff)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["user"]["account"]["email"] is None
    assert body["credentials"]["delivery"] == "temporary_password"
    temporary = body["credentials"]["temporary_password"]
    assert temporary and len(temporary) >= 12

    first = await login(client, "no.email.kid", temporary)
    assert first["user"]["must_change_password"] is True

    # Staff members still need an email.
    staff_without_email = await client.post(
        f"{API}/users",
        json={
            "role": "staff",
            "account": {"username": "no.mail.staff"},
            "personal_info": {"first_name": "No", "last_name": "Mail", "phone": "+919800000001"},
            "employment": {"employee_code": "EMP-NM"},
        },
        headers=hierarchy.head,
    )
    assert staff_without_email.status_code == 422
    assert "account.email" in {d["field"] for d in staff_without_email.json()["details"]}

    # Emailed creation reports how access was delivered.
    emailed = student_payload("with.email.kid")
    emailed["account"].pop("password")
    assert (await client.post(f"{API}/users", json=emailed, headers=hierarchy.staff)).json()["credentials"] == {
        "delivery": "email_link",
        "temporary_password": None,
    }


async def test_manager_sets_a_temporary_password(client: AsyncClient, hierarchy: Hierarchy) -> None:
    url = f"{API}/users/{hierarchy.student_id}/password"
    weak = await client.post(url, json={"new_password": "short"}, headers=hierarchy.staff)
    assert weak.status_code == 422

    response = await client.post(url, json={"new_password": "Temp!Classroom#2026"}, headers=hierarchy.staff)
    assert response.status_code == 200, response.text
    # Old sessions end and the student must choose a new password.
    assert (await client.get(f"{API}/users/me", headers=hierarchy.student)).status_code == 401
    assert (await login(client, "student1", "Temp!Classroom#2026"))["user"]["must_change_password"] is True
    assert (
        await client.post(f"{API}/auth/login", json={"identifier": "student1", "password": NEW_PASSWORD})
    ).status_code == 401

    # Students cannot set passwords for others.
    denied = await client.post(
        f"{API}/users/{hierarchy.staff_id}/password",
        json={"new_password": "Temp!Classroom#2026"},
        headers=hierarchy.student,
    )
    assert denied.status_code in (401, 403, 404)


async def test_audit_log_is_scoped_to_the_viewer(client: AsyncClient, hierarchy: Hierarchy) -> None:
    await client.patch(
        f"{API}/users/{hierarchy.student_id}/status",
        json={"status": "suspended", "reason": "Fee dues"},
        headers=hierarchy.head,
    )

    head_view = await client.get(f"{API}/audit-logs", params={"action": "user.status_changed"}, headers=hierarchy.head)
    assert head_view.status_code == 200, head_view.text
    entry = head_view.json()["audit_logs"][0]
    assert entry["actor"]["user_id"] == hierarchy.head_id
    assert entry["target"] == {"type": "user", "id": hierarchy.student_id, "name": "Student Test"}
    assert entry["institution"]["organization_id"] == hierarchy.organization_id
    assert entry["details"]["reason"] == "Fee dues"

    history = await client.get(
        f"{API}/audit-logs", params={"user_id": hierarchy.student_id, "category": "user"}, headers=hierarchy.admin
    )
    assert {log["action"] for log in history.json()["audit_logs"]} >= {"user.created", "user.status_changed"}

    # Sign-ins inside the institution are visible to its head; other institutions' entries are not.
    logins = (await client.get(f"{API}/audit-logs", params={"category": "auth"}, headers=hierarchy.head)).json()[
        "audit_logs"
    ]
    assert logins and all(log["institution"]["organization_id"] == hierarchy.organization_id for log in logins)
    other = await client.post(f"{API}/institutions", json=institution_payload("OTHER-01"), headers=hierarchy.admin)
    assert other.status_code == 201
    created = (
        await client.get(f"{API}/audit-logs", params={"action": "institution.created"}, headers=hierarchy.head)
    ).json()["audit_logs"]
    assert [log["institution"]["organization_id"] for log in created] == [hierarchy.organization_id]

    assert (await client.get(f"{API}/audit-logs", headers=hierarchy.staff)).status_code == 403
    root = await client.get(f"{API}/audit-logs", params={"per_page": 5}, headers=hierarchy.root)
    assert root.json()["page_context"]["per_page"] == 5 and root.json()["audit_logs"][0]["audit_log_id"]
