"""Request examples shown in Swagger UI (/docs). Keep in sync with docs/API.md."""

from typing import Any

from app.core.ids import EXAMPLE_ORGANIZATION_ID, EXAMPLE_USER_ID


def _example(summary: str, value: dict[str, Any], description: str | None = None) -> dict[str, Any]:
    example: dict[str, Any] = {"summary": summary, "value": value}
    if description:
        example["description"] = description
    return example


HYDERABAD_ADDRESS = {
    "line1": "Plot 42, Road No. 5",
    "line2": "Jubilee Hills",
    "city": "Hyderabad",
    "state": "Telangana",
    "postal_code": "500033",
    "country": "IN",
}

CREATE_USER = {
    "student": _example(
        "Create a student",
        {
            "role": "student",
            "organization_id": EXAMPLE_ORGANIZATION_ID,
            "account": {"email": "aarav.reddy@example.com"},
            "personal_info": {
                "first_name": "Aarav",
                "last_name": "Reddy",
                "gender": "male",
                "date_of_birth": "2012-04-15",
            },
            "address": HYDERABAD_ADDRESS,
            "student": {
                "admission_number": "ADM/2024/0457",
                "admission_date": "2024-06-01",
                "guardians": [
                    {
                        "full_name": "Suresh Reddy",
                        "relationship": "father",
                        "phone": "+919876543210",
                        "email": "suresh.reddy@example.com",
                        "occupation": "Engineer",
                        "is_primary": True,
                    }
                ],
            },
        },
        "Username is generated (aarav.reddy) and a set-up link is emailed because no password is sent.",
    ),
    "staff": _example(
        "Create a staff member",
        {
            "role": "staff",
            "organization_id": EXAMPLE_ORGANIZATION_ID,
            "account": {"email": "priya.sharma@example.com", "username": "priya.sharma"},
            "personal_info": {
                "first_name": "Priya",
                "last_name": "Sharma",
                "gender": "female",
                "phone": "+919812345678",
            },
            "employment": {
                "employee_code": "EMP-1024",
                "designation": "Mathematics Teacher",
                "department": "Mathematics",
                "employment_type": "full_time",
                "date_of_joining": "2023-06-12",
            },
        },
    ),
    "institution_head": _example(
        "Create an institution head",
        {
            "role": "institution_head",
            "organization_id": EXAMPLE_ORGANIZATION_ID,
            "account": {"email": "ramesh.iyer@example.com"},
            "personal_info": {"first_name": "Ramesh", "last_name": "Iyer", "phone": "+919900112233"},
            "employment": {"employee_code": "EMP-0001", "designation": "Principal", "employment_type": "full_time"},
        },
    ),
}

UPDATE_USER = {
    "contact": _example(
        "Change phone and designation",
        {"personal_info": {"phone": "+919812300000"}, "employment": {"designation": "Senior Mathematics Teacher"}},
    ),
    "guardians": _example(
        "Replace a student's guardians",
        {
            "student": {
                "guardians": [
                    {
                        "full_name": "Suresh Reddy",
                        "relationship": "father",
                        "phone": "+919876543210",
                        "is_primary": True,
                    },
                    {"full_name": "Kavya Reddy", "relationship": "mother", "phone": "+919876500000"},
                ]
            }
        },
    ),
    "move": _example(
        "Move to another institution and manager",
        {"organization_id": EXAMPLE_ORGANIZATION_ID, "manager_user_id": EXAMPLE_USER_ID},
    ),
}

CREATE_ADMIN = {
    "admin": _example(
        "Create an admin",
        {
            "account": {"email": "anita.verma@example.com"},
            "personal_info": {"first_name": "Anita", "last_name": "Verma", "phone": "+919845012345"},
            "employment": {"designation": "Regional Education Manager"},
        },
    )
}

CREATE_INSTITUTION = {
    "school": _example(
        "Create a school",
        {
            "name": "Springfield High School",
            "code": "SPH-HYD",
            "type": "school",
            "admin_user_id": EXAMPLE_USER_ID,
            "contact": {
                "email": "office@springfieldhigh.edu.in",
                "phone": "+914023456789",
                "website": "https://www.springfieldhigh.edu.in",
            },
            "address": HYDERABAD_ADDRESS,
            "timezone": "Asia/Kolkata",
            "registration_number": "TS-SCH-2004-1187",
            "affiliation": "CBSE",
            "established_year": 2004,
        },
        "admin_user_id is required when a super admin creates the institution and must be omitted by admins.",
    )
}
