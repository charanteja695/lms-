"""Bulk user import from CSV.

Every row goes through exactly the same rules as ``POST /users`` (permissions, formats, role rules,
uniqueness), plus duplicate checks inside the file. Modes:

* ``dry_run=true``        validate only, write nothing (show the report before importing)
* ``all_or_nothing``      create every row in one transaction, or none if any row is invalid
* ``skip_invalid``        create the valid rows, report the invalid ones

Imported users never receive a password in the file: each gets an account set-up email, or (students without
email) a temporary password that appears once in the import result.
"""

import csv
import io
from enum import StrEnum
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppError, BadRequestError, ConflictError, ValidationFailedError
from app.db.session import commit_or_conflict
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.audit_service import AuditAction
from app.services.user_service import PreparedUser, ReservedIdentities, UserService

IMPORT_COLUMNS = [
    "role", "organization_id", "manager_user_id",
    "email", "username",
    "first_name", "middle_name", "last_name", "gender", "date_of_birth",
    "phone", "alternate_phone", "preferred_language", "timezone",
    "address_line1", "address_line2", "city", "state", "postal_code", "country",
    "employee_code", "designation", "department", "employment_type", "date_of_joining",
    "admission_number", "admission_date", "program", "branch", "year_of_study", "section", "graduation_year", "cgpa",
    "guardian_name", "guardian_relationship", "guardian_phone", "guardian_email", "guardian_occupation",
]  # fmt: skip
REQUIRED_COLUMNS = ("role", "email", "first_name", "last_name")  # email may be blank for students

_SECTIONS: dict[str, dict[str, str]] = {
    "account": {"email": "email", "username": "username"},
    "personal_info": {
        name: name
        for name in (
            "first_name",
            "middle_name",
            "last_name",
            "gender",
            "date_of_birth",
            "phone",
            "alternate_phone",
            "preferred_language",
            "timezone",
        )
    },  # fmt: skip
    "address": {
        "address_line1": "line1",
        "address_line2": "line2",
        "city": "city",
        "state": "state",
        "postal_code": "postal_code",
        "country": "country",
    },  # fmt: skip
    "employment": {
        name: name for name in ("employee_code", "designation", "department", "employment_type", "date_of_joining")
    },
    "student": {
        name: name
        for name in (
            "admission_number",
            "admission_date",
            "program",
            "branch",
            "year_of_study",
            "section",
            "graduation_year",
            "cgpa",
        )
    },  # fmt: skip
}
_GUARDIAN = {
    "guardian_name": "full_name",
    "guardian_relationship": "relationship",
    "guardian_phone": "phone",
    "guardian_email": "email",
    "guardian_occupation": "occupation",
}
# request field path -> CSV column, for error reports
_FIELD_TO_COLUMN = {
    f"{section}.{field}": column for section, fields in _SECTIONS.items() for column, field in fields.items()
}
_FIELD_TO_COLUMN.update({f"student.guardians.0.{field}": column for column, field in _GUARDIAN.items()})
_FIELD_TO_COLUMN.update({"student.guardians": "guardian_name", "address": "postal_code"})

TEMPLATE_ROWS = [
    {
        "role": "staff", "email": "priya.sharma@example.com", "first_name": "Priya", "last_name": "Sharma",
        "gender": "female", "phone": "+919812345678", "employee_code": "EMP-1024",
        "designation": "Mathematics Teacher", "department": "Mathematics", "employment_type": "full_time",
        "date_of_joining": "2023-06-12",
    },
    {
        "role": "student", "email": "aarav.reddy@example.com", "first_name": "Aarav", "last_name": "Reddy",
        "gender": "male", "date_of_birth": "2012-04-15", "address_line1": "Plot 42, Road No. 5", "city": "Hyderabad",
        "state": "Telangana", "postal_code": "500033", "country": "IN", "admission_number": "ADM/2024/0457",
        "admission_date": "2024-06-01", "program": "Class 8", "section": "B", "guardian_name": "Suresh Reddy", "guardian_relationship": "father",
        "guardian_phone": "+919876543210",
    },
]  # fmt: skip


class ImportMode(StrEnum):
    SKIP_INVALID = "skip_invalid"
    ALL_OR_NOTHING = "all_or_nothing"


REPORT_COLUMNS = ["row", "result", "user_id", "username", "email", "temporary_password", "column", "code", "message"]


def report_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    """One line per created user and per problem, for the downloadable import report."""
    keys = ("row", "user_id", "username", "email", "temporary_password")
    lines: list[dict[str, Any]] = [
        {**{k: user.get(k) for k in keys}, "result": "created"} for user in result["created_users"]
    ]
    lines += [{**error, "result": "error"} for error in result["errors"]]
    return sorted(lines, key=lambda line: (line["row"], line["result"]))


def template_csv() -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=IMPORT_COLUMNS, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(TEMPLATE_ROWS)
    return "﻿" + buffer.getvalue()


def _row_payload(row: dict[str, str]) -> dict[str, Any]:
    values = {key: value.strip() for key, value in row.items() if key and value is not None and value.strip() != ""}
    payload: dict[str, Any] = {
        key: values[key] for key in ("role", "organization_id", "manager_user_id") if key in values
    }
    for section, fields in _SECTIONS.items():
        section_values = {field: values[column] for column, field in fields.items() if column in values}
        if section_values or section in ("account", "personal_info"):
            payload[section] = section_values
    guardian = {field: values[column] for column, field in _GUARDIAN.items() if column in values}
    if guardian:
        payload.setdefault("student", {})["guardians"] = [guardian]
    return payload


def _column_for(field: str | None) -> str | None:
    if not field:
        return None
    return _FIELD_TO_COLUMN.get(field, field.rsplit(".", 1)[-1])


class ImportService:
    def __init__(self, users: UserService) -> None:
        self.users = users
        self.settings = users.settings

    async def import_users(
        self,
        actor: User,
        content: bytes,
        *,
        dry_run: bool,
        mode: ImportMode,
        max_rows: int | None = None,
        max_bytes: int | None = None,
    ) -> dict[str, Any]:
        rows = self._read_rows(
            content, max_rows or self.settings.IMPORT_MAX_ROWS, max_bytes or self.settings.IMPORT_MAX_FILE_BYTES
        )
        reserved = ReservedIdentities()
        prepared: list[tuple[int, PreparedUser]] = []
        errors: list[dict[str, Any]] = []

        for index, row in enumerate(rows):
            row_number = index + 2  # header is row 1
            try:
                data = UserCreate.model_validate(_row_payload(row))
            except ValidationError as exc:
                errors.extend(self._validation_errors(row_number, exc))
                continue
            try:
                prepared.append((row_number, await self.users.prepare_user(actor, data, reserved=reserved)))
            except AppError as exc:
                errors.extend(self._app_errors(row_number, exc))

        invalid_rows = len({error["row"] for error in errors})
        created: list[dict[str, Any]] = []
        should_write = not dry_run and prepared and not (mode == ImportMode.ALL_OR_NOTHING and errors)
        if should_write:
            created = await self._write(actor, prepared, errors, mode)
            invalid_rows = len({error["row"] for error in errors})

        return {
            "dry_run": dry_run,
            "mode": mode,
            "total_rows": len(rows),
            "valid_rows": len(prepared),
            "invalid_rows": invalid_rows,
            "created": len(created),
            "created_users": created,
            "errors": sorted(errors, key=lambda e: e["row"]),
        }

    async def _write(
        self, actor: User, prepared: list[tuple[int, PreparedUser]], errors: list[dict[str, Any]], mode: ImportMode
    ) -> list[dict[str, Any]]:
        db = self.users.db
        created: list[tuple[int, PreparedUser, str | None]] = []
        if mode == ImportMode.ALL_OR_NOTHING:
            try:
                for row_number, item in prepared:
                    created.append((row_number, item, await self.users.persist_user(actor, item)))
                await db.flush()
            except IntegrityError as exc:
                await db.rollback()
                raise ConflictError(
                    "Some rows conflict with records created meanwhile. Nothing was imported.", code="IMPORT_CONFLICT"
                ) from exc
        else:
            for row_number, item in prepared:
                try:
                    async with db.begin_nested():  # a conflicting row only undoes itself
                        token = await self.users.persist_user(actor, item)
                        await db.flush()
                    created.append((row_number, item, token))
                except IntegrityError:
                    errors.append(
                        {
                            "row": row_number,
                            "column": None,
                            "code": "DUPLICATE_DATA",
                            "message": "This row conflicts with a record created meanwhile",
                        }
                    )
        self._audit(actor, len(created), mode)
        await commit_or_conflict(db, "The import could not be saved. Nothing was imported.")

        for _, item, token in created:
            self.users.notify_created(item.user, token)
        return [
            {
                "row": row_number,
                "user_id": str(item.user.public_id),
                "email": item.user.email,
                "username": item.user.username,
                "temporary_password": item.password if item.password_generated else None,
            }
            for row_number, item, _ in created
        ]

    def _audit(self, actor: User, count: int, mode: ImportMode) -> None:
        self.users.audit.log(
            AuditAction.USERS_IMPORTED,
            actor_id=actor.id,
            resource_type="user",
            institution_id=actor.institution_id,
            details={"created": count, "mode": mode},
        )

    def _read_rows(self, content: bytes, max_rows: int, max_bytes: int) -> list[dict[str, str]]:
        if len(content) > max_bytes:
            raise BadRequestError(
                f"The file is larger than {max_bytes // (1024 * 1024)} MB.",
                code="FILE_TOO_LARGE",
            )
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise BadRequestError("Save the file as CSV UTF-8 and try again.", code="INVALID_FILE_ENCODING") from exc

        reader = csv.DictReader(io.StringIO(text))
        headers = [(name or "").strip().lower() for name in (reader.fieldnames or [])]
        reader.fieldnames = headers
        details = [
            {"field": column, "code": "MISSING_COLUMN", "message": f"Column '{column}' is required"}
            for column in REQUIRED_COLUMNS
            if column not in headers
        ]
        details += [
            {"field": column or "(blank)", "code": "UNKNOWN_COLUMN", "message": "Not a supported column"}
            for column in headers
            if column not in IMPORT_COLUMNS
        ]
        if details:
            raise ValidationFailedError(
                "The file's columns do not match the import template.", code="INVALID_COLUMNS", details=details
            )

        rows = []
        for row in reader:
            if any((value or "").strip() for value in row.values() if isinstance(value, str)):
                rows.append(row)
            if len(rows) > max_rows:
                hint = " Use a background import for larger files." if max_rows == self.settings.IMPORT_MAX_ROWS else ""
                raise BadRequestError(f"Import at most {max_rows:,} rows per file.{hint}", code="TOO_MANY_ROWS")
        if not rows:
            raise BadRequestError("The file has no data rows.", code="EMPTY_FILE")
        return rows

    @staticmethod
    def _validation_errors(row_number: int, exc: ValidationError) -> list[dict[str, Any]]:
        from app.core.error_handlers import _validation_detail

        errors = []
        for error in exc.errors():
            detail = _validation_detail({**error, "loc": ("body", *error["loc"])})
            errors.append(
                {
                    "row": row_number,
                    "column": _column_for(detail["field"]),
                    "code": detail["code"],
                    "message": detail["message"],
                }
            )
        return errors

    @staticmethod
    def _app_errors(row_number: int, exc: AppError) -> list[dict[str, Any]]:
        if exc.details:
            return [
                {
                    "row": row_number,
                    "column": _column_for(d.get("field")),
                    "code": d.get("code", exc.code),
                    "message": d["message"],
                }
                for d in exc.details
            ]
        return [{"row": row_number, "column": None, "code": exc.code, "message": exc.message}]
