"""Role-specific data rules, checked against the final state of a user record.

Format rules (valid phone, real date, …) are enforced by the request schemas. These rules
depend on the role and on other fields, so they run after a create/update has been applied
to the model, before anything is written. All problems are reported together.

Employer roles (employer_admin, recruiter) follow the admin column.

| Rule                                   | admin | institution_head | staff | student |
|----------------------------------------|:-----:|:----------------:|:-----:|:-------:|
| account.email required                 |  yes  |       yes        |  yes  |   no    |
| personal_info.phone required           |  yes  |       yes        |  yes  |   no    |
| personal_info.date_of_birth required   |  no   |        no        |  no   |   yes   |
| minimum age (EMPLOYEE/STUDENT_MIN_AGE) |  18   |        18        |  18   |    3    |
| employment allowed                     |  yes  |       yes        |  yes  |   no    |
| employment.employee_code required      |  no   |       yes        |  yes  |   –     |
| student section required               |  no   |        no        |  no   |   yes   |
| guardian required below 18             |   –   |        –         |   –   |   yes   |
"""

from datetime import date
from typing import Any

from app.core.config import Settings
from app.models.user import User
from app.permissions.roles import Role
from app.schemas.types import age_on


def _problem(field: str, code: str, message: str) -> dict[str, Any]:
    return {"field": field, "code": code, "message": message}


def user_record_problems(user: User, settings: Settings, *, today: date | None = None) -> list[dict[str, Any]]:
    """``user.profile``, ``employment``, ``student`` and ``guardians`` must be loaded or assigned."""
    today = today or date.today()
    problems: list[dict[str, Any]] = []
    role = Role(user.role)
    birth_date = user.profile.date_of_birth if user.profile else None
    age = age_on(birth_date, today) if birth_date else None

    if role == Role.STUDENT:
        if birth_date is None:
            problems.append(
                _problem("personal_info.date_of_birth", "REQUIRED", "Date of birth is required for students")
            )
        elif age is not None and age < settings.STUDENT_MIN_AGE:
            problems.append(
                _problem(
                    "personal_info.date_of_birth",
                    "AGE_TOO_LOW",
                    f"Students must be at least {settings.STUDENT_MIN_AGE} years old",
                )
            )
        if user.employment is not None:
            problems.append(_problem("employment", "NOT_ALLOWED", "Students cannot have employment details"))
        if user.student is None:
            problems.append(_problem("student", "REQUIRED", "Student details are required for students"))
        elif age is not None and age < settings.GUARDIAN_REQUIRED_BELOW_AGE and not user.guardians:
            problems.append(
                _problem(
                    "student.guardians",
                    "REQUIRED",
                    f"At least one guardian is required for students under {settings.GUARDIAN_REQUIRED_BELOW_AGE}",
                )
            )
        return problems

    # admin, institution_head, staff, employer_admin, recruiter
    if not user.email:
        problems.append(_problem("account.email", "REQUIRED", f"Email is required for {role} users"))
    if not user.phone:
        problems.append(_problem("personal_info.phone", "REQUIRED", f"Phone number is required for {role} users"))
    if age is not None and age < settings.EMPLOYEE_MIN_AGE:
        problems.append(
            _problem(
                "personal_info.date_of_birth",
                "AGE_TOO_LOW",
                f"{role} users must be at least {settings.EMPLOYEE_MIN_AGE} years old",
            )
        )
    if user.student is not None:
        problems.append(_problem("student", "NOT_ALLOWED", "Only students can have student details"))
    if role in (Role.INSTITUTION_HEAD, Role.STAFF) and (user.employment is None or not user.employment.employee_code):
        problems.append(
            _problem(
                "employment.employee_code", "REQUIRED", "Employee code is required for institution heads and staff"
            )
        )
    if user.employment is not None and user.employment.date_of_joining and birth_date:
        if user.employment.date_of_joining <= birth_date:
            problems.append(
                _problem("employment.date_of_joining", "INVALID_DATE", "Date of joining must be after date of birth")
            )
    return problems
