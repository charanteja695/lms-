"""Bulk user import from CSV."""

import csv
import io

from httpx import AsyncClient

from tests.conftest import API, NEW_PASSWORD, CapturingEmailSender, Hierarchy, login

HEADER = [
    "role", "email", "username", "first_name", "last_name", "gender", "date_of_birth", "phone",
    "employee_code", "designation", "admission_number", "guardian_name", "guardian_relationship", "guardian_phone",
]  # fmt: skip


def _csv(rows: list[dict[str, str]], header: list[str] = HEADER) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=header)
    writer.writeheader()
    writer.writerows(rows)
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def _student(n: int, **overrides: str) -> dict[str, str]:
    row = {
        "role": "student",
        "email": f"import.student{n}@example.com",
        "first_name": "Import",
        "last_name": f"Student{'abcdefghij'[n]}",
        "date_of_birth": "2013-02-01",
        "admission_number": f"IMP-{n:03d}",
        "guardian_name": "Parent Name",
        "guardian_relationship": "mother",
        "guardian_phone": f"+9197000000{n:02d}",
    }
    row.update(overrides)
    return row


async def _upload(client: AsyncClient, headers: dict[str, str], content: bytes, **form: str) -> dict:  # type: ignore[type-arg]
    response = await client.post(
        f"{API}/users/import",
        files={"file": ("users.csv", content, "text/csv")},
        data=form,
        headers=headers,
    )
    return {**response.json(), "http_status": response.status_code}


async def test_template_download(client: AsyncClient, hierarchy: Hierarchy) -> None:
    response = await client.get(f"{API}/users/import/template", headers=hierarchy.head)
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text.lstrip("﻿"))))
    assert [r["role"] for r in rows] == ["staff", "student"]


async def test_dry_run_reports_every_problem_without_writing(client: AsyncClient, hierarchy: Hierarchy) -> None:
    rows = [
        _student(1),
        _student(2, phone="12", date_of_birth="15/04/2013"),
        _student(3, email="import.student1@example.com", admission_number="IMP-001"),
        _student(4, role="staff"),
    ]
    body = await _upload(client, hierarchy.head, _csv(rows), dry_run="true")
    assert body["http_status"] == 200, body
    result = body["import_result"]
    assert (result["total_rows"], result["valid_rows"], result["invalid_rows"], result["created"]) == (4, 1, 3, 0)
    by_row = {(e["row"], e["column"], e["code"]) for e in result["errors"]}
    assert (3, "phone", "INVALID_PHONE") in by_row
    assert (3, "date_of_birth", "INVALID_DATE") in by_row
    assert (4, "email", "DUPLICATE_IN_FILE") in by_row
    assert (4, "admission_number", "DUPLICATE_IN_FILE") in by_row
    assert (5, "phone", "REQUIRED") in by_row
    assert (5, "employee_code", "REQUIRED") in by_row

    listed = (await client.get(f"{API}/users", params={"search_text": "import"}, headers=hierarchy.head)).json()
    assert listed["page_context"]["total_records"] == 0


async def test_all_or_nothing_and_skip_invalid(
    client: AsyncClient, hierarchy: Hierarchy, emails: CapturingEmailSender
) -> None:
    rows = [_student(1), _student(2), _student(3, guardian_phone="bad")]

    refused = await _upload(client, hierarchy.head, _csv(rows), mode="all_or_nothing")
    assert refused["import_result"]["created"] == 0
    assert refused["message"].startswith("Nothing was imported")

    partial = await _upload(client, hierarchy.head, _csv(rows), mode="skip_invalid")
    result = partial["import_result"]
    assert result["created"] == 2 and result["invalid_rows"] == 1
    assert [u["row"] for u in result["created_users"]] == [2, 3]
    assert result["created_users"][0]["username"] == "import.studenta"[:-1] + "b"  # generated from the name

    # Imported users set their password through the emailed link, then log in.
    user = await client.get(f"{API}/users/{result['created_users'][0]['user_id']}", headers=hierarchy.head)
    assert user.json()["user"]["manager"]["user_id"] == hierarchy.head_id
    token = emails.link_token_for("import.student1@example.com")
    setup = await client.post(
        f"{API}/auth/reset-password",
        json={"reset_token": token, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
    )
    assert setup.status_code == 200, setup.text
    await login(client, "import.student1@example.com", NEW_PASSWORD)

    # Re-importing the same file finds the existing records.
    again = await _upload(client, hierarchy.head, _csv(rows[:2]), dry_run="true")
    assert {e["code"] for e in again["import_result"]["errors"]} >= {"DUPLICATE_EMAIL", "DUPLICATE_ADMISSION_NUMBER"}


async def test_file_level_errors(client: AsyncClient, hierarchy: Hierarchy) -> None:
    missing = await _upload(client, hierarchy.head, _csv([{"role": "student"}], header=["role", "shoe_size"]))
    assert missing["http_status"] == 422
    assert {d["code"] for d in missing["details"]} == {"MISSING_COLUMN", "UNKNOWN_COLUMN"}

    empty = await _upload(client, hierarchy.head, _csv([]))
    assert empty["code"] == "EMPTY_FILE"

    not_utf8 = await _upload(client, hierarchy.head, "role,email\nstudent,é@x.com".encode("utf-16"))
    assert not_utf8["code"] in {"INVALID_FILE_ENCODING", "INVALID_COLUMNS"}

    assert (await _upload(client, hierarchy.student, _csv([_student(1)])))["http_status"] == 403


async def test_staff_can_only_import_students(client: AsyncClient, hierarchy: Hierarchy) -> None:
    rows = [
        _student(1),
        {"role": "staff", "email": "sneaky@example.com", "first_name": "Sneaky", "last_name": "Staff",
         "phone": "+919811112222", "employee_code": "EMP-X"},
    ]  # fmt: skip
    body = await _upload(client, hierarchy.staff, _csv(rows), mode="skip_invalid")
    result = body["import_result"]
    assert result["created"] == 1
    assert result["errors"][0]["code"] == "PERMISSION_DENIED"
