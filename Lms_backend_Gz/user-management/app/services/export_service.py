"""Streaming CSV exports.

Exports page through the table by primary key (keyset pagination) in short transactions and
stream each batch straight to the client, so memory and database load stay flat whether the
export has 50 rows or 500,000. Filters and access scope are the same SQL conditions the list
endpoints use, so an export never contains a row its caller could not see.
"""

import csv
import io
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.interfaces import ORMOption

from app.models.institution import Institution
from app.models.user import User
from app.repositories.institution_repository import InstitutionRepository

# Callers reach these (including Institution/User, re-exported here rather than imported a second time from
# app.models) as export_service.<name> alongside stream_csv/export_filename, so they must be listed for
# mypy's --no-implicit-reexport (implied by --strict) to allow it.
__all__ = [
    "EMPLOYER_EXPORT_COLUMNS",
    "INSTITUTION_COUNTS_LOADER",
    "INSTITUTION_EXPORT_COLUMNS",
    "INSTITUTION_EXPORT_OPTIONS",
    "Institution",
    "USER_EXPORT_COLUMNS",
    "USER_EXPORT_OPTIONS",
    "User",
    "export_filename",
    "stream_csv",
]

Getter = Callable[[Any, Any], Any]
ExtraLoader = Callable[[AsyncSession, list[Any]], Awaitable[Any]]

_NUMERIC = re.compile(r"^[+-]?[0-9]+(\.[0-9]+)?$")


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    # Spreadsheet formula injection: neutralise cells a spreadsheet would evaluate.
    if text[:1] in ("=", "@", "\t", "\r") or (text[:1] in ("+", "-") and not _NUMERIC.fullmatch(text)):
        return f"'{text}"
    return text


def _csv_line(values: Sequence[Any]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\r\n").writerow([_cell(v) for v in values])
    return buffer.getvalue()


async def stream_csv[ExportModel: (User, Institution)](
    # Constrained (not bound): checked once per listed type, so `model.id` below is verified against User and
    # Institution individually — a plain `type[User] | type[Institution]` union loses that to SQLAlchemy's
    # `select()` overloads and widens `model` to the common `Base`, which has no `id` of its own (see
    # UUIDPrimaryKeyMixin).
    sessionmaker: async_sessionmaker[AsyncSession],
    model: type[ExportModel],
    conditions: list[ColumnElement[bool]] | None,
    columns: Sequence[tuple[str, Getter]],
    *,
    options: Sequence[ORMOption],
    max_rows: int,
    batch_size: int,
    extra_loader: ExtraLoader | None = None,
    on_rows: Callable[[int], None] | None = None,
) -> AsyncIterator[bytes]:
    # UTF-8 BOM so spreadsheet apps show non-Latin names (e.g. Telugu, Hindi) correctly.
    yield ("﻿" + _csv_line([name for name, _ in columns])).encode("utf-8")
    if conditions is None:
        return

    last_id = None
    sent = 0
    while sent < max_rows:
        limit = min(batch_size, max_rows - sent)
        async with sessionmaker() as db:
            stmt = select(model).where(*conditions)
            if last_id is not None:
                stmt = stmt.where(model.id > last_id)
            stmt = stmt.order_by(model.id).limit(limit).options(*options)
            rows = list((await db.execute(stmt)).unique().scalars().all())
            if not rows:
                return
            extra = await extra_loader(db, rows) if extra_loader else None
            chunk = "".join(_csv_line([getter(row, extra) for _, getter in columns]) for row in rows)
        yield chunk.encode("utf-8")
        if on_rows is not None:
            on_rows(len(rows))
        sent += len(rows)
        last_id = rows[-1].id
        if len(rows) < limit:
            return


# ====================================================================== users


def _profile(attr: str) -> Getter:
    return lambda u, _: getattr(u.profile, attr) if u.profile else None


def _employment(attr: str) -> Getter:
    return lambda u, _: getattr(u.employment, attr) if u.employment else None


def _primary_guardian(attr: str) -> Getter:
    def get(user: User, _: Any) -> Any:
        guardian = next((g for g in user.guardians if g.is_primary), None)
        return getattr(guardian, attr) if guardian else None

    return get


USER_EXPORT_OPTIONS: tuple[ORMOption, ...] = (
    joinedload(User.institution),
    joinedload(User.manager),
    joinedload(User.created_by),
    selectinload(User.profile),
    selectinload(User.employment),
    selectinload(User.student),
    selectinload(User.guardians),
)

USER_EXPORT_COLUMNS: list[tuple[str, Getter]] = [
    ("user_id", lambda u, _: u.public_id),
    ("role", lambda u, _: u.role),
    ("status", lambda u, _: u.status),
    ("first_name", lambda u, _: u.first_name),
    ("middle_name", lambda u, _: u.middle_name),
    ("last_name", lambda u, _: u.last_name),
    ("email", lambda u, _: u.email),
    ("email_verified", lambda u, _: u.email_verified_at is not None),
    ("username", lambda u, _: u.username),
    ("phone", lambda u, _: u.phone),
    ("alternate_phone", _profile("alternate_phone")),
    ("gender", _profile("gender")),
    ("date_of_birth", _profile("date_of_birth")),
    ("preferred_language", _profile("preferred_language")),
    ("timezone", _profile("timezone")),
    ("address_line1", _profile("address_line1")),
    ("address_line2", _profile("address_line2")),
    ("city", _profile("city")),
    ("state", _profile("state")),
    ("postal_code", _profile("postal_code")),
    ("country", _profile("country")),
    ("organization_id", lambda u, _: u.institution.public_id if u.institution else None),
    ("institution_name", lambda u, _: u.institution.name if u.institution else None),
    ("institution_code", lambda u, _: u.institution.code if u.institution else None),
    ("manager_user_id", lambda u, _: u.manager.public_id if u.manager else None),
    ("manager_name", lambda u, _: u.manager.full_name if u.manager else None),
    ("employee_code", _employment("employee_code")),
    ("designation", _employment("designation")),
    ("department", _employment("department")),
    ("employment_type", _employment("employment_type")),
    ("date_of_joining", _employment("date_of_joining")),
    ("admission_number", lambda u, _: u.student.admission_number if u.student else None),
    ("admission_date", lambda u, _: u.student.admission_date if u.student else None),
    ("program", lambda u, _: u.student.program if u.student else None),
    ("branch", lambda u, _: u.student.branch if u.student else None),
    ("year_of_study", lambda u, _: u.student.year_of_study if u.student else None),
    ("section", lambda u, _: u.student.section if u.student else None),
    ("graduation_year", lambda u, _: u.student.graduation_year if u.student else None),
    ("cgpa", lambda u, _: u.student.cgpa if u.student else None),
    ("primary_guardian_name", _primary_guardian("full_name")),
    ("primary_guardian_relationship", _primary_guardian("relationship_type")),
    ("primary_guardian_phone", _primary_guardian("phone")),
    ("created_by_user_id", lambda u, _: u.created_by.public_id if u.created_by else None),
    ("last_login_time", lambda u, _: u.last_login_at),
    ("created_time", lambda u, _: u.created_at),
    ("modified_time", lambda u, _: u.updated_at),
]


# ====================================================================== institutions


async def _institution_counts(db: AsyncSession, rows: list[Any]) -> dict[Any, dict[str, int]]:
    return await InstitutionRepository(db).member_counts([row.id for row in rows])


def _count(role: str) -> Getter:
    return lambda i, counts: counts.get(i.id, {}).get(role, 0)


INSTITUTION_EXPORT_OPTIONS: tuple[ORMOption, ...] = (joinedload(Institution.admin),)
INSTITUTION_COUNTS_LOADER: ExtraLoader = _institution_counts

INSTITUTION_EXPORT_COLUMNS: list[tuple[str, Getter]] = [
    ("organization_id", lambda i, _: i.public_id),
    ("name", lambda i, _: i.name),
    ("code", lambda i, _: i.code),
    ("type", lambda i, _: i.institution_type),
    ("status", lambda i, _: i.status),
    ("email", lambda i, _: i.email),
    ("phone", lambda i, _: i.phone),
    ("alternate_phone", lambda i, _: i.alternate_phone),
    ("website", lambda i, _: i.website),
    ("address_line1", lambda i, _: i.address_line1),
    ("address_line2", lambda i, _: i.address_line2),
    ("city", lambda i, _: i.city),
    ("state", lambda i, _: i.state),
    ("postal_code", lambda i, _: i.postal_code),
    ("country", lambda i, _: i.country),
    ("timezone", lambda i, _: i.timezone),
    ("registration_number", lambda i, _: i.registration_number),
    ("affiliation", lambda i, _: i.affiliation),
    ("established_year", lambda i, _: i.established_year),
    ("admin_user_id", lambda i, _: i.admin.public_id),
    ("admin_name", lambda i, _: i.admin.full_name),
    ("institution_heads", _count("institution_head")),
    ("staff", _count("staff")),
    ("students", _count("student")),
    ("created_time", lambda i, _: i.created_at),
    ("modified_time", lambda i, _: i.updated_at),
]


def export_filename(resource: str) -> str:
    return f"{resource}-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.csv"


EMPLOYER_EXPORT_COLUMNS: list[tuple[str, Getter]] = [
    ("organization_id", lambda i, _: i.public_id),
    ("name", lambda i, _: i.name),
    ("code", lambda i, _: i.code),
    ("industry", lambda i, _: i.industry),
    ("status", lambda i, _: i.status),
    ("email", lambda i, _: i.email),
    ("phone", lambda i, _: i.phone),
    ("website", lambda i, _: i.website),
    ("city", lambda i, _: i.city),
    ("state", lambda i, _: i.state),
    ("country", lambda i, _: i.country),
    ("registration_number", lambda i, _: i.registration_number),
    ("established_year", lambda i, _: i.established_year),
    ("admin_user_id", lambda i, _: i.admin.public_id),
    ("admin_name", lambda i, _: i.admin.full_name),
    ("employer_admins", _count("employer_admin")),
    ("recruiters", _count("recruiter")),
    ("created_time", lambda i, _: i.created_at),
    ("modified_time", lambda i, _: i.updated_at),
]
