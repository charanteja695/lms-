"""Filters, pagination limits and CSV exports."""

import csv
import io
from datetime import date, timedelta

from httpx import AsyncClient

from app.core.config import get_settings
from tests.conftest import (
    API,
    Hierarchy,
    activate_account,
    admin_payload,
    create_user,
    institution_payload,
    staff_payload,
    student_payload,
)


def _rows(response_text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(response_text.lstrip("﻿"))))


async def test_user_filters(client: AsyncClient, hierarchy: Hierarchy) -> None:
    maths = staff_payload("maths.teacher")
    maths["personal_info"]["gender"] = "female"
    maths["employment"].update({"department": "Mathematics", "employment_type": "part_time"})
    await create_user(client, hierarchy.head, maths)

    async def user_ids(**params: object) -> list[str]:
        response = await client.get(f"{API}/users", params=params, headers=hierarchy.admin)
        assert response.status_code == 200, response.text
        return [u["username"] for u in response.json()["users"]]

    assert await user_ids(gender="female") == ["maths.teacher"]
    assert await user_ids(department="mathematics") == ["maths.teacher"]
    assert await user_ids(employment_type="part_time") == ["maths.teacher"]
    assert set(await user_ids(role="staff")) == {"staff1", "maths.teacher"}
    assert await user_ids(organization_id=hierarchy.organization_id, role="student") == ["student1"]
    assert await user_ids(
        created_by_user_id=hierarchy.head_id, role="staff", sort_column="first_name", sort_order="asc"
    ) == [
        "maths.teacher",
        "staff1",
    ]
    assert await user_ids(email_verified=True) == []
    today = date.today()
    assert len(await user_ids(created_from=today.isoformat(), created_to=today.isoformat())) == 4
    assert await user_ids(created_from=(today + timedelta(days=1)).isoformat()) == []
    assert await user_ids(organization_id="4602118326954090497") == []


async def test_invalid_date_range_and_list_window(client: AsyncClient, hierarchy: Hierarchy) -> None:
    bad_range = await client.get(
        f"{API}/users", params={"created_from": "2026-02-01", "created_to": "2026-01-01"}, headers=hierarchy.admin
    )
    assert bad_range.status_code == 422

    too_deep = await client.get(f"{API}/users", params={"page": 101, "per_page": 100}, headers=hierarchy.admin)
    assert too_deep.status_code == 422
    assert "export" in too_deep.json()["details"][0]["message"]

    short_search = await client.get(f"{API}/users", params={"search_text": "a"}, headers=hierarchy.admin)
    assert short_search.status_code == 422


async def test_page_context_reports_exact_totals(client: AsyncClient, hierarchy: Hierarchy) -> None:
    body = (await client.get(f"{API}/users", params={"per_page": 2}, headers=hierarchy.admin)).json()
    assert body["page_context"]["total_records"] == 3
    assert body["page_context"]["total_is_exact"] is True
    assert body["page_context"]["has_more_page"] is True


async def test_user_export_respects_scope_and_filters(client: AsyncClient, hierarchy: Hierarchy) -> None:
    response = await client.get(f"{API}/users/export", headers=hierarchy.head)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].startswith('attachment; filename="users-')
    rows = _rows(response.text)
    assert {r["username"] for r in rows} == {"staff1", "student1"}  # never the head's own account or other roles

    student = next(r for r in rows if r["role"] == "student")
    assert student["user_id"] == hierarchy.student_id
    assert student["organization_id"] == hierarchy.organization_id
    assert student["admission_number"] == "ADM/STUDENT1"
    assert student["primary_guardian_relationship"] == "father"
    assert student["manager_user_id"] == hierarchy.staff_id
    assert student["phone"] == ""

    filtered = _rows((await client.get(f"{API}/users/export", params={"role": "staff"}, headers=hierarchy.head)).text)
    assert [r["username"] for r in filtered] == ["staff1"]

    assert (await client.get(f"{API}/users/export", headers=hierarchy.student)).status_code == 403


async def test_export_streams_in_batches(client: AsyncClient, hierarchy: Hierarchy) -> None:
    for index in range(5):
        payload = student_payload(f"batch.student{chr(97 + index)}")
        await create_user(client, hierarchy.staff, payload)

    settings = get_settings()
    original = settings.EXPORT_BATCH_SIZE, settings.EXPORT_MAX_ROWS
    settings.EXPORT_BATCH_SIZE, settings.EXPORT_MAX_ROWS = 100, 4
    try:
        capped = _rows((await client.get(f"{API}/users/export", headers=hierarchy.staff)).text)
    finally:
        settings.EXPORT_BATCH_SIZE, settings.EXPORT_MAX_ROWS = original
    assert len(capped) == 4

    everything = _rows((await client.get(f"{API}/users/export", headers=hierarchy.staff)).text)
    assert len(everything) == 6
    assert len({r["user_id"] for r in everything}) == 6


async def test_export_neutralises_spreadsheet_formulas(client: AsyncClient, hierarchy: Hierarchy) -> None:
    payload = staff_payload("formula.staff")
    payload["employment"]["designation"] = '=HYPERLINK("http://evil")'
    await create_user(client, hierarchy.head, payload)
    rows = _rows(
        (await client.get(f"{API}/users/export", params={"search_text": "formula"}, headers=hierarchy.head)).text
    )
    assert rows[0]["designation"].startswith("'=")
    assert rows[0]["phone"].startswith("+91")  # plain numbers are left untouched


async def test_institution_and_admin_exports(client: AsyncClient, hierarchy: Hierarchy) -> None:
    await client.post(f"{API}/admins", json=admin_payload("admin2"), headers=hierarchy.root)
    admin2 = await activate_account(client, "admin2")
    await client.post(f"{API}/institutions", json=institution_payload("SHV", affiliation="ICSE"), headers=admin2)

    own = _rows((await client.get(f"{API}/institutions/export", headers=hierarchy.admin)).text)
    assert [r["organization_id"] for r in own] == [hierarchy.organization_id]
    assert (own[0]["institution_heads"], own[0]["staff"], own[0]["students"]) == ("1", "1", "1")

    all_rows = _rows((await client.get(f"{API}/institutions/export", headers=hierarchy.root)).text)
    assert len(all_rows) == 2
    icse = _rows(
        (await client.get(f"{API}/institutions/export", params={"affiliation": "icse"}, headers=hierarchy.root)).text
    )
    assert [r["code"] for r in icse] == ["SHV"]

    listed = (
        await client.get(
            f"{API}/institutions", params={"city": "HYDERABAD", "state": "telangana"}, headers=hierarchy.root
        )
    ).json()
    assert listed["page_context"]["total_records"] == 2

    admins = _rows((await client.get(f"{API}/admins/export", headers=hierarchy.root)).text)
    assert {r["username"] for r in admins} == {"admin1", "admin2"}
    assert (await client.get(f"{API}/admins/export", headers=hierarchy.admin)).status_code == 403


async def test_exports_are_audited(client: AsyncClient, app, hierarchy: Hierarchy) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.models import AuditLog

    await client.get(f"{API}/users/export", params={"role": "student"}, headers=hierarchy.head)
    async with app.state.sessionmaker() as db:
        entries = (await db.execute(select(AuditLog).where(AuditLog.action == "user.exported"))).scalars().all()
    assert len(entries) == 1
    assert entries[0].details["filters"]["role"] == "student"


async def test_purge_expired(client: AsyncClient, app, hierarchy: Hierarchy) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import func, select, update

    from app.cli.maintenance import purge_expired
    from app.core.time import utcnow
    from app.models import RefreshToken, UserSession

    # Age every session past the retention window, as if they ended long ago.
    long_ago = utcnow() - timedelta(days=get_settings().SESSION_RETENTION_DAYS + 1)
    async with app.state.sessionmaker() as db:
        before = (await db.execute(select(func.count()).select_from(UserSession))).scalar_one()
        await db.execute(update(UserSession).values(revoked_at=long_ago))
        await db.commit()

    totals = await purge_expired(get_settings(), sessionmaker=app.state.sessionmaker, batch_size=2)
    assert totals["user_sessions"] == before > 0
    async with app.state.sessionmaker() as db:
        assert (await db.execute(select(func.count()).select_from(UserSession))).scalar_one() == 0
        assert (await db.execute(select(func.count()).select_from(RefreshToken))).scalar_one() == 0
    _ = staff_payload
