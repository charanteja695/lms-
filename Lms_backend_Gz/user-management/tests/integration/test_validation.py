"""Input validation and response-shape guarantees."""

import re
from datetime import date, timedelta
from typing import Any

from httpx import AsyncClient

from tests.conftest import API, Hierarchy, staff_payload, student_payload

UUID_PATTERN = re.compile(r"[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}", re.IGNORECASE)


def _fields(response: Any) -> dict[str, str]:
    body = response.json()
    assert body["status"] == "error", body
    return {d["field"]: d["code"] for d in body["details"]}


async def test_no_internal_ids_in_any_response(client: AsyncClient, hierarchy: Hierarchy) -> None:
    urls = [
        (hierarchy.admin, f"{API}/users"),
        (hierarchy.admin, f"{API}/users/{hierarchy.student_id}"),
        (hierarchy.admin, f"{API}/institutions"),
        (hierarchy.admin, f"{API}/institutions/{hierarchy.organization_id}"),
        (hierarchy.root, f"{API}/admins"),
        (hierarchy.root, f"{API}/admins/{hierarchy.admin_id}"),
        (hierarchy.student, f"{API}/users/me"),
        (hierarchy.student, f"{API}/auth/sessions"),
    ]
    for headers, url in urls:
        response = await client.get(url, headers=headers)
        assert response.status_code == 200, (url, response.text)
        assert not UUID_PATTERN.search(response.text), f"internal id leaked from {url}"
        assert '"id"' not in response.text


async def test_ids_are_strings_everywhere(client: AsyncClient, hierarchy: Hierarchy) -> None:
    user = (await client.get(f"{API}/users/{hierarchy.student_id}", headers=hierarchy.staff)).json()["user"]
    for value in (user["user_id"], user["institution"]["organization_id"], user["manager"]["user_id"]):
        assert isinstance(value, str) and value.isdigit()


async def test_malformed_ids_are_not_found(client: AsyncClient, hierarchy: Hierarchy) -> None:
    for bad in ("abc", "123", "00000000000000000001", "1" * 30):
        response = await client.get(f"{API}/users/{bad}", headers=hierarchy.admin)
        assert response.status_code == 404
        assert response.json()["code"] == "USER_NOT_FOUND"
    response = await client.get(f"{API}/institutions/not-a-number", headers=hierarchy.admin)
    assert response.json()["code"] == "INSTITUTION_NOT_FOUND"


async def test_numeric_json_ids_are_rejected(client: AsyncClient, hierarchy: Hierarchy) -> None:
    payload = staff_payload("numeric.id", organization_id=int(hierarchy.organization_id))
    response = await client.post(f"{API}/users", json=payload, headers=hierarchy.admin)
    assert response.status_code == 422
    assert _fields(response)["organization_id"] == "INVALID_ID"


async def test_field_format_errors_are_all_reported(client: AsyncClient, hierarchy: Hierarchy) -> None:
    payload = staff_payload("x")
    payload["account"] = {"email": "not-an-email", "username": "9starts-with-digit", "extra": 1}
    payload["personal_info"] = {
        "first_name": "R2D2",
        "last_name": "   ",
        "phone": "12345",
        "gender": "robot",
        "timezone": "Mars/Olympus",
        "preferred_language": "english",
    }
    payload["address"] = {"line1": "x", "city": "Hyderabad", "state": "TS", "postal_code": "12", "country": "XX"}
    response = await client.post(f"{API}/users", json=payload, headers=hierarchy.head)
    assert response.status_code == 422
    fields = _fields(response)
    assert fields == {
        "account.email": "INVALID_EMAIL",
        "account.username": "INVALID_USERNAME",
        "account.extra": "UNKNOWN_FIELD",
        "personal_info.first_name": "INVALID_NAME",
        "personal_info.last_name": "REQUIRED",
        "personal_info.phone": "INVALID_PHONE",
        "personal_info.gender": "INVALID_OPTION",
        "personal_info.timezone": "INVALID_TIMEZONE",
        "personal_info.preferred_language": "INVALID_LANGUAGE",
        "address.postal_code": "INVALID_POSTAL_CODE",
        "address.country": "INVALID_COUNTRY",
    }


async def test_international_names_are_accepted(client: AsyncClient, hierarchy: Hierarchy) -> None:
    payload = staff_payload("telugu.name")
    payload["personal_info"].update({"first_name": "నాగార్జున", "last_name": "O'Brien-Rao"})
    response = await client.post(f"{API}/users", json=payload, headers=hierarchy.head)
    assert response.status_code == 201, response.text
    assert response.json()["user"]["personal_info"]["full_name"] == "నాగార్జున O'Brien-Rao"


async def test_role_rules_are_reported_together(client: AsyncClient, hierarchy: Hierarchy) -> None:
    student = student_payload("rules.student")
    del student["personal_info"]["date_of_birth"]
    student["employment"] = {"designation": "Monitor"}
    response = await client.post(f"{API}/users", json=student, headers=hierarchy.staff)
    assert response.status_code == 422
    assert _fields(response) == {"personal_info.date_of_birth": "REQUIRED", "employment": "NOT_ALLOWED"}

    staff = staff_payload("rules.staff")
    del staff["personal_info"]["phone"]
    staff["employment"] = {"designation": "Teacher"}
    response = await client.post(f"{API}/users", json=staff, headers=hierarchy.head)
    assert _fields(response) == {"personal_info.phone": "REQUIRED", "employment.employee_code": "REQUIRED"}


async def test_date_rules(client: AsyncClient, hierarchy: Hierarchy) -> None:
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    future = student_payload("future.kid")
    future["personal_info"]["date_of_birth"] = tomorrow
    assert _fields(await client.post(f"{API}/users", json=future, headers=hierarchy.staff)) == {
        "personal_info.date_of_birth": "DATE_IN_FUTURE"
    }

    toddler = student_payload("toddler")
    toddler["personal_info"]["date_of_birth"] = (date.today() - timedelta(days=365)).isoformat()
    assert _fields(await client.post(f"{API}/users", json=toddler, headers=hierarchy.staff)) == {
        "personal_info.date_of_birth": "AGE_TOO_LOW"
    }

    no_guardian = student_payload("no.guardian")
    no_guardian["student"]["guardians"] = []
    assert _fields(await client.post(f"{API}/users", json=no_guardian, headers=hierarchy.staff)) == {
        "student.guardians": "REQUIRED"
    }

    adult = student_payload("adult.learner")
    adult["personal_info"]["date_of_birth"] = "1990-01-01"
    adult["student"]["guardians"] = []
    assert (await client.post(f"{API}/users", json=adult, headers=hierarchy.staff)).status_code == 201

    wrong_format = student_payload("wrong.format")
    wrong_format["personal_info"]["date_of_birth"] = "15/04/2012"
    assert _fields(await client.post(f"{API}/users", json=wrong_format, headers=hierarchy.staff)) == {
        "personal_info.date_of_birth": "INVALID_DATE"
    }


async def test_guardian_rules(client: AsyncClient, hierarchy: Hierarchy) -> None:
    payload = student_payload("two.primaries")
    payload["student"]["guardians"] = [
        {"full_name": "A One", "relationship": "father", "phone": "+919811111111", "is_primary": True},
        {"full_name": "B Two", "relationship": "mother", "phone": "+919822222222", "is_primary": True},
    ]
    response = await client.post(f"{API}/users", json=payload, headers=hierarchy.staff)
    assert response.status_code == 422
    assert _fields(response) == {"student.guardians": "INVALID_VALUE"}


async def test_query_parameters_are_validated(client: AsyncClient, hierarchy: Hierarchy) -> None:
    response = await client.get(
        f"{API}/users", params={"per_page": 500, "sort_column": "password", "unknown": 1}, headers=hierarchy.admin
    )
    assert response.status_code == 422
    assert _fields(response) == {
        "per_page": "OUT_OF_RANGE",
        "sort_column": "INVALID_OPTION",
        "unknown": "UNKNOWN_FIELD",
    }


async def test_empty_update_is_rejected(client: AsyncClient, hierarchy: Hierarchy) -> None:
    response = await client.put(f"{API}/users/{hierarchy.student_id}", json={}, headers=hierarchy.staff)
    assert response.status_code == 422


async def test_institution_validation(client: AsyncClient, hierarchy: Hierarchy) -> None:
    response = await client.post(
        f"{API}/institutions",
        json={
            "name": "X",
            "code": "bad code!",
            "type": "castle",
            "contact": {"email": "office@example.com", "phone": "+914023456789", "website": "ftp://example.com"},
            "address": {
                "line1": "1 Road",
                "city": "Hyderabad",
                "state": "TS",
                "postal_code": "500081",
                "country": "IN",
            },
            "established_year": 2999,
        },
        headers=hierarchy.admin,
    )
    assert response.status_code == 422
    assert _fields(response) == {
        "name": "TOO_SHORT",
        "code": "INVALID_INSTITUTION_CODE",
        "type": "INVALID_OPTION",
        "contact.website": "INVALID_URL",
        "established_year": "INVALID_YEAR",
    }

    by_super_admin = await client.post(
        f"{API}/institutions",
        json={
            "name": "No Owner School",
            "code": "NOOWN",
            "type": "school",
            "contact": {"email": "office@example.com", "phone": "+914023456789"},
            "address": {
                "line1": "1 Road",
                "city": "Hyderabad",
                "state": "TS",
                "postal_code": "500081",
                "country": "IN",
            },
        },
        headers=hierarchy.root,
    )
    assert _fields(by_super_admin) == {"admin_user_id": "REQUIRED"}


async def test_updates_are_not_blocked_by_existing_gaps(client: AsyncClient, app, hierarchy: Hierarchy) -> None:  # type: ignore[no-untyped-def]
    """Imported records may miss data (here: guardians). Unrelated edits still work; new problems are refused."""
    from sqlalchemy import delete

    from app.models import StudentGuardian

    async with app.state.sessionmaker() as db:
        await db.execute(delete(StudentGuardian))
        await db.commit()

    url = f"{API}/users/{hierarchy.student_id}"
    unrelated = await client.put(
        url, json={"personal_info": {"alternate_phone": "+919000022222"}}, headers=hierarchy.staff
    )
    assert unrelated.status_code == 200, unrelated.text

    new_problem = await client.put(url, json={"personal_info": {"date_of_birth": None}}, headers=hierarchy.staff)
    assert new_problem.status_code == 422
    assert _fields(new_problem) == {"personal_info.date_of_birth": "REQUIRED"}
