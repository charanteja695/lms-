"""Password strength rules applied whenever a password is set by a person."""

import string

from app.core.exceptions import ValidationFailedError

PASSWORD_MAX_LENGTH = 128

# Small built-in deny list; swap for a breached-password service (e.g. k-anonymity
# lookup) when one is available.
_COMMON_PASSWORDS = frozenset(
    {
        "password",
        "password1",
        "password123",
        "passw0rd",
        "p@ssw0rd",
        "p@ssword123",
        "123456789012",
        "qwertyuiop",
        "qwerty123456",
        "iloveyou1234",
        "welcome123",
        "admin123456",
        "administrator",
        "letmein12345",
        "changeme1234",
        "superadmin123",
    }
)


def password_problems(
    password: str,
    *,
    min_length: int,
    email: str | None = None,
    username: str | None = None,
) -> list[str]:
    problems: list[str] = []
    if len(password) < min_length:
        problems.append(f"Password must be at least {min_length} characters long")
    if len(password) > PASSWORD_MAX_LENGTH:
        problems.append(f"Password must be at most {PASSWORD_MAX_LENGTH} characters long")
    if not any(c.islower() for c in password):
        problems.append("Password must contain a lowercase letter")
    if not any(c.isupper() for c in password):
        problems.append("Password must contain an uppercase letter")
    if not any(c.isdigit() for c in password):
        problems.append("Password must contain a digit")
    if not any(c in string.punctuation or (not c.isalnum() and not c.isspace()) for c in password):
        problems.append("Password must contain a special character")
    if password.strip() != password:
        problems.append("Password must not start or end with whitespace")

    lowered = password.lower()
    if lowered in _COMMON_PASSWORDS:
        problems.append("Password is too common")
    for personal in (username, email.split("@", 1)[0] if email else None):
        if personal and len(personal) >= 3 and personal.lower() in lowered:
            problems.append("Password must not contain your username or email")
            break
    return problems


def ensure_strong_password(
    password: str,
    *,
    min_length: int,
    email: str | None = None,
    username: str | None = None,
    field: str = "password",
) -> None:
    problems = password_problems(password, min_length=min_length, email=email, username=username)
    if problems:
        raise ValidationFailedError(
            "The password does not meet the security requirements.",
            code="WEAK_PASSWORD",
            details=[{"field": field, "code": "WEAK_PASSWORD", "message": problem} for problem in problems],
        )
