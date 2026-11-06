"""Validated field types. Every request field is built from these, so each rule lives in one place.

Validators raise ``PydanticCustomError`` with an UPPER_SNAKE code and a human sentence;
the error handler turns them into ``{"field", "code", "message"}`` entries.
"""

import re
import unicodedata
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Annotated, Any
from urllib.parse import urlsplit
from zoneinfo import available_timezones

import phonenumbers
from pydantic import AfterValidator, BeforeValidator, Field, PlainSerializer, WithJsonSchema
from pydantic_core import PydanticCustomError

from app.core.config import get_settings
from app.core.ids import EXAMPLE_ORGANIZATION_ID, EXAMPLE_SESSION_ID, EXAMPLE_USER_ID, parse_public_id

# ------------------------------------------------------------------ helpers

_BIDI_CONTROLS = frozenset("‪‫‬‭‮⁦⁧⁨⁩")
_ZERO_WIDTH_JOINERS = frozenset("‌‍")  # needed by several Indic scripts
_WHITESPACE_RUN = re.compile(r"\s+")


def _error(code: str, message: str) -> PydanticCustomError:
    return PydanticCustomError(code, message)


def _require_str(value: Any) -> str:
    if not isinstance(value, str):
        raise _error("INVALID_TYPE", "Must be a string")
    return value


def _clean_text(value: str, *, min_length: int, max_length: int) -> str:
    value = _WHITESPACE_RUN.sub(" ", unicodedata.normalize("NFC", value)).strip()
    for char in value:
        if char in _BIDI_CONTROLS or unicodedata.category(char) in {"Cc", "Cs", "Co"}:
            raise _error("INVALID_CHARACTERS", "Must not contain control or invisible formatting characters")
    if len(value) < min_length:
        raise _error("REQUIRED" if not value else "TOO_SHORT", f"Must be at least {min_length} characters")
    if len(value) > max_length:
        raise _error("TOO_LONG", f"Must be at most {max_length} characters")
    return value


def _string_type(validator: Any, *, max_length: int, examples: list[str] | None = None, **schema: Any) -> Any:
    json_schema: dict[str, Any] = {"type": "string", "maxLength": max_length, **schema}
    if examples:
        json_schema["examples"] = examples
    return Annotated[str, BeforeValidator(_require_str), AfterValidator(validator), WithJsonSchema(json_schema)]


def text(max_length: int, *, min_length: int = 1, examples: list[str] | None = None) -> Any:
    """Free text: trimmed, whitespace collapsed, Unicode-normalised, no control characters."""
    return _string_type(
        lambda v: _clean_text(v, min_length=min_length, max_length=max_length),
        max_length=max_length,
        minLength=min_length,
        examples=examples,
    )


# ------------------------------------------------------------------ identifiers


def _id_type(label: str, example: str) -> Any:
    def validate(value: Any) -> int:
        number = parse_public_id(value)
        if number is None:
            raise _error("INVALID_ID", f'Must be a valid {label} (a numeric string such as "{example}")')
        return number

    return Annotated[
        int,
        BeforeValidator(validate),
        WithJsonSchema({"type": "string", "pattern": r"^[1-9][0-9]{9,18}$", "examples": [example]}),
    ]


UserId = _id_type("user_id", EXAMPLE_USER_ID)
OrganizationId = _id_type("organization_id", EXAMPLE_ORGANIZATION_ID)
SessionId = _id_type("session_id", EXAMPLE_SESSION_ID)

# Output: 64-bit ids are always serialised as strings (JavaScript numbers lose precision above 2^53).
PublicIdOut = Annotated[
    int, PlainSerializer(str, return_type=str), WithJsonSchema({"type": "string", "examples": [EXAMPLE_USER_ID]})
]


def _utc_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


Timestamp = Annotated[
    datetime,
    PlainSerializer(_utc_timestamp, return_type=str),
    WithJsonSchema({"type": "string", "format": "date-time", "examples": ["2026-09-16T10:30:00Z"]}),
]

# ------------------------------------------------------------------ people


_NAME_PUNCTUATION = frozenset(" .'-’")


def _validate_person_name(value: str, max_length: int) -> str:
    value = _clean_text(value, min_length=1, max_length=max_length)
    has_letter = False
    for char in value:
        category = unicodedata.category(char)
        if category.startswith("L"):
            has_letter = True
        elif not (category.startswith("M") or char in _NAME_PUNCTUATION or char in _ZERO_WIDTH_JOINERS):
            raise _error("INVALID_NAME", "May contain only letters, spaces, apostrophes, hyphens and periods")
    if not has_letter:
        raise _error("INVALID_NAME", "Must contain at least one letter")
    return value


def person_name(max_length: int, example: str) -> Any:
    return _string_type(lambda v: _validate_person_name(v, max_length), max_length=max_length, examples=[example])


FirstName = person_name(50, "Priya")
MiddleName = person_name(50, "Lakshmi")
LastName = person_name(50, "Sharma")
FullName = person_name(100, "Ramesh Sharma")


RESERVED_USERNAMES = frozenset(
    {
        "admin", "administrator", "root", "system", "sysadmin", "superadmin", "super_admin", "support",
        "help", "api", "auth", "login", "logout", "me", "null", "undefined", "anonymous", "security",
        "owner", "lms", "staff", "student", "teacher", "principal", "noreply", "no-reply", "postmaster",
    }
)  # fmt: skip
_USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


def _validate_username(value: str) -> str:
    value = value.strip().lower()
    if not 3 <= len(value) <= 30:
        raise _error("INVALID_USERNAME", "Must be 3 to 30 characters")
    if not _USERNAME_PATTERN.fullmatch(value):
        raise _error(
            "INVALID_USERNAME",
            "Must start with a letter and contain only letters, digits and single . _ - between them",
        )
    if value in RESERVED_USERNAMES:
        raise _error("RESERVED_USERNAME", "This username is reserved")
    return value


Username = _string_type(_validate_username, max_length=30, minLength=3, examples=["priya.sharma"])


def _validate_email(value: str) -> str:
    from email_validator import EmailNotValidError, validate_email

    value = value.strip()
    if len(value) > 254:
        raise _error("INVALID_EMAIL", "Must be at most 254 characters")
    try:
        result = validate_email(value, check_deliverability=False)
    except EmailNotValidError as exc:
        raise _error("INVALID_EMAIL", "Enter a valid email address") from exc
    return result.normalized.lower()


EmailAddress = _string_type(_validate_email, max_length=254, format="email", examples=["priya.sharma@example.com"])


def _validate_phone(value: str) -> str:
    raw = value.strip()
    invalid = _error("INVALID_PHONE", "Enter a valid phone number, e.g. +919876543210")
    if not re.fullmatch(r"\+?[0-9][0-9 ()./-]{5,24}", raw):
        raise invalid
    region = None if raw.startswith("+") else get_settings().DEFAULT_COUNTRY_CODE
    try:
        parsed = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException as exc:
        raise invalid from exc
    if not phonenumbers.is_valid_number(parsed):
        raise invalid
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


PhoneNumber = _string_type(_validate_phone, max_length=25, examples=["+919876543210"])


def _age_on(birth_date: date, today: date) -> int:
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def age_on(birth_date: date, today: date | None = None) -> int:
    return _age_on(birth_date, today or date.today())


def _validate_past_date(value: date) -> date:
    if value > date.today():
        raise _error("DATE_IN_FUTURE", "Cannot be in the future")
    if value.year < 1900:
        raise _error("INVALID_DATE", "Must be after 1900")
    return value


def _validate_date_of_birth(value: date) -> date:
    _validate_past_date(value)
    if age_on(value) > 120:
        raise _error("INVALID_DATE_OF_BIRTH", "Date of birth is not realistic")
    return value


_ISO_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def _parse_date(value: Any) -> date:
    """Accept only ``YYYY-MM-DD`` strings (or date objects), never numbers or timestamps."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str) and _ISO_DATE.fullmatch(value.strip()):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            pass
    raise _error("INVALID_DATE", "Must be a real date in YYYY-MM-DD format")


_DATE_SCHEMA = {"type": "string", "format": "date"}
FilterDate = Annotated[date, BeforeValidator(_parse_date), WithJsonSchema({**_DATE_SCHEMA, "examples": ["2026-01-01"]})]
PastDate = Annotated[
    date,
    BeforeValidator(_parse_date),
    AfterValidator(_validate_past_date),
    WithJsonSchema({**_DATE_SCHEMA, "examples": ["2024-06-01"]}),
]
DateOfBirth = Annotated[
    date,
    BeforeValidator(_parse_date),
    AfterValidator(_validate_date_of_birth),
    WithJsonSchema({**_DATE_SCHEMA, "examples": ["2012-04-15"]}),
]

# ------------------------------------------------------------------ places & locale


@lru_cache
def _country_codes() -> frozenset[str]:
    return frozenset(code for code in phonenumbers.SUPPORTED_REGIONS if len(code) == 2)


def _validate_country(value: str) -> str:
    value = value.strip().upper()
    if value not in _country_codes():
        raise _error("INVALID_COUNTRY", "Use a 2-letter ISO 3166 country code, e.g. IN")
    return value


CountryCode = _string_type(_validate_country, max_length=2, minLength=2, examples=["IN"])


@lru_cache
def _timezones() -> frozenset[str]:
    return frozenset(available_timezones())


def _validate_timezone(value: str) -> str:
    value = value.strip()
    if value not in _timezones():
        raise _error("INVALID_TIMEZONE", "Use an IANA time zone name, e.g. Asia/Kolkata")
    return value


TimeZoneName = _string_type(_validate_timezone, max_length=64, examples=["Asia/Kolkata"])


def _validate_language(value: str) -> str:
    parts = value.strip().replace("_", "-").split("-")
    if not (1 <= len(parts) <= 2 and re.fullmatch(r"[A-Za-z]{2,3}", parts[0])) or (
        len(parts) == 2 and not re.fullmatch(r"[A-Za-z]{2}", parts[1])
    ):
        raise _error("INVALID_LANGUAGE", "Use a language code such as en, hi, te or en-IN")
    return parts[0].lower() + (f"-{parts[1].upper()}" if len(parts) == 2 else "")


LanguageCode = _string_type(_validate_language, max_length=6, examples=["en-IN"])

_POSTAL_CODE_RULES = {
    "IN": (re.compile(r"^[1-9][0-9]{5}$"), "Indian PIN codes have 6 digits, e.g. 500081"),
    "US": (re.compile(r"^[0-9]{5}(?:-[0-9]{4})?$"), "US ZIP codes look like 94105 or 94105-1234"),
}


def _validate_postal_code(value: str) -> str:
    value = _WHITESPACE_RUN.sub(" ", value.strip().upper())
    if not re.fullmatch(r"[A-Z0-9](?:[A-Z0-9 -]{1,10})[A-Z0-9]", value):
        raise _error("INVALID_POSTAL_CODE", "Enter a valid postal code")
    return value


def check_postal_code_for_country(postal_code: str, country: str) -> str | None:
    """Country-specific format check; returns an error message or ``None``."""
    rule = _POSTAL_CODE_RULES.get(country)
    if rule and not rule[0].fullmatch(postal_code):
        return rule[1]
    return None


PostalCode = _string_type(_validate_postal_code, max_length=12, examples=["500081"])


def _validate_url(value: str) -> str:
    value = value.strip()
    parts = urlsplit(value)
    if (
        len(value) > 255
        or parts.scheme not in {"http", "https"}
        or not parts.hostname
        or "." not in parts.hostname
        or parts.username
        or parts.password
    ):
        raise _error("INVALID_URL", "Enter a full website address, e.g. https://www.example.edu")
    return value


WebsiteUrl = _string_type(_validate_url, max_length=255, format="uri", examples=["https://www.springfieldhigh.edu.in"])


def _validate_year(value: int) -> int:
    if not 1800 <= value <= datetime.now(UTC).year:
        raise _error("INVALID_YEAR", f"Must be between 1800 and {datetime.now(UTC).year}")
    return value


Year = Annotated[
    int, Field(strict=True), AfterValidator(_validate_year), WithJsonSchema({"type": "integer", "examples": [1998]})
]

# ------------------------------------------------------------------ codes


def _code_type(label: str, *, min_length: int, max_length: int, example: str, allow_slash: bool) -> Any:
    extra = "/" if allow_slash else ""
    pattern = re.compile(rf"^[A-Z0-9](?:[A-Z0-9_{re.escape(extra)}-]*[A-Z0-9])?$")

    def validate(value: str) -> str:
        value = value.strip().upper()
        if not min_length <= len(value) <= max_length or not pattern.fullmatch(value):
            allowed = "letters, digits, - and _" + (" and /" if allow_slash else "")
            raise _error(
                f"INVALID_{label.upper()}",
                f"Must be {min_length}-{max_length} characters using {allowed}, starting and ending with a letter or digit",
            )
        return value

    return _string_type(validate, max_length=max_length, minLength=min_length, examples=[example])


InstitutionCode = _code_type("institution_code", min_length=2, max_length=20, example="SPH-HYD", allow_slash=False)
EmployeeCode = _code_type("employee_code", min_length=1, max_length=30, example="EMP-1024", allow_slash=True)
AdmissionNumber = _code_type("admission_number", min_length=1, max_length=30, example="ADM/2024/0457", allow_slash=True)

# ------------------------------------------------------------------ secrets & misc

Password = Annotated[
    str,
    Field(strict=True, min_length=1, max_length=128),
    WithJsonSchema({"type": "string", "format": "password", "maxLength": 128}),
]
Identifier = _string_type(
    lambda v: _clean_text(v, min_length=3, max_length=254).lower(),
    max_length=254,
    minLength=3,
    examples=["priya.sharma@example.com"],
)
Reason = text(500, min_length=3, examples=["Fee payment pending"])
OpaqueToken = Annotated[str, Field(strict=True, min_length=20, max_length=512)]
