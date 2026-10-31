"""Seed repeatable demo accounts for ExamLMS.

Creates 3 demo accounts for each role:
- SUPER_ADMIN
- ADMIN
- INSTITUTION_HEAD
- STAFF
- STUDENT

Ensures valid institutions, employment profiles, student profiles, and unique passwords.
Idempotent: accounts that already exist are skipped and never overwritten.
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import date
from pathlib import Path

# Add app directory to sys.path if running as script
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from sqlalchemy import select

from app.core.config import get_settings
from app.core.ids import new_public_id
from app.core.security import hash_password
from app.core.time import utcnow
from app.db.session import build_engine, build_sessionmaker
from app.db.types import uuid7
from app.models import EmploymentProfile, Institution, StudentProfile, User, UserProfile
from app.permissions.roles import OrganizationType, Role, UserStatus

DEMO_ACCOUNTS_DATA = [
    # 1. SUPER_ADMIN
    {
        "role": Role.SUPER_ADMIN,
        "name": "Demo Super Admin 1",
        "first_name": "Demo",
        "last_name": "Super Admin 1",
        "email": "demo.superadmin1@example.com",
        "username": "demo.superadmin1",
        "password": "Sup3r!Admin#Demo1",
        "scopes": None,
        "inst_idx": None,
    },
    {
        "role": Role.SUPER_ADMIN,
        "name": "Demo Super Admin 2",
        "first_name": "Demo",
        "last_name": "Super Admin 2",
        "email": "demo.superadmin2@example.com",
        "username": "demo.superadmin2",
        "password": "Sup3r!Admin#Demo2",
        "scopes": None,
        "inst_idx": None,
    },
    {
        "role": Role.SUPER_ADMIN,
        "name": "Demo Super Admin 3",
        "first_name": "Demo",
        "last_name": "Super Admin 3",
        "email": "demo.superadmin3@example.com",
        "username": "demo.superadmin3",
        "password": "Sup3r!Admin#Demo3",
        "scopes": None,
        "inst_idx": None,
    },
    # 2. ADMIN
    {
        "role": Role.ADMIN,
        "name": "Demo Admin 1",
        "first_name": "Demo",
        "last_name": "Admin 1",
        "email": "demo.admin1@example.com",
        "username": "demo.admin1",
        "password": "Adm1n!Demo#Acct1",
        "scopes": ",accounts.manage,support.manage,analytics.view,",
        "inst_idx": None,
    },
    {
        "role": Role.ADMIN,
        "name": "Demo Admin 2",
        "first_name": "Demo",
        "last_name": "Admin 2",
        "email": "demo.admin2@example.com",
        "username": "demo.admin2",
        "password": "Adm1n!Demo#Acct2",
        "scopes": ",accounts.manage,support.manage,analytics.view,",
        "inst_idx": None,
    },
    {
        "role": Role.ADMIN,
        "name": "Demo Admin 3",
        "first_name": "Demo",
        "last_name": "Admin 3",
        "email": "demo.admin3@example.com",
        "username": "demo.admin3",
        "password": "Adm1n!Demo#Acct3",
        "scopes": ",accounts.manage,support.manage,analytics.view,",
        "inst_idx": None,
    },
    # 3. INSTITUTION_HEAD
    {
        "role": Role.INSTITUTION_HEAD,
        "name": "Demo Institution Head 1",
        "first_name": "Demo",
        "last_name": "Head 1",
        "email": "demo.head1@example.com",
        "username": "demo.head1",
        "password": "H3ad!Inst#Demo1",
        "scopes": None,
        "inst_idx": 0,
        "employee_code": "EMP-HEAD-01",
        "designation": "Principal & Director",
        "department": "Administration",
    },
    {
        "role": Role.INSTITUTION_HEAD,
        "name": "Demo Institution Head 2",
        "first_name": "Demo",
        "last_name": "Head 2",
        "email": "demo.head2@example.com",
        "username": "demo.head2",
        "password": "H3ad!Inst#Demo2",
        "scopes": None,
        "inst_idx": 1,
        "employee_code": "EMP-HEAD-02",
        "designation": "Head of Institution",
        "department": "Administration",
    },
    {
        "role": Role.INSTITUTION_HEAD,
        "name": "Demo Institution Head 3",
        "first_name": "Demo",
        "last_name": "Head 3",
        "email": "demo.head3@example.com",
        "username": "demo.head3",
        "password": "H3ad!Inst#Demo3",
        "scopes": None,
        "inst_idx": 2,
        "employee_code": "EMP-HEAD-03",
        "designation": "Dean of Academics",
        "department": "Administration",
    },
    # 4. STAFF
    {
        "role": Role.STAFF,
        "name": "Demo Staff 1",
        "first_name": "Demo",
        "last_name": "Staff 1",
        "email": "demo.staff1@example.com",
        "username": "demo.staff1",
        "password": "St4ff!Prof#Demo1",
        "scopes": None,
        "inst_idx": 0,
        "employee_code": "EMP-STAFF-01",
        "designation": "Senior Professor",
        "department": "Computer Science",
    },
    {
        "role": Role.STAFF,
        "name": "Demo Staff 2",
        "first_name": "Demo",
        "last_name": "Staff 2",
        "email": "demo.staff2@example.com",
        "username": "demo.staff2",
        "password": "St4ff!Prof#Demo2",
        "scopes": None,
        "inst_idx": 1,
        "employee_code": "EMP-STAFF-02",
        "designation": "Associate Professor",
        "department": "Engineering",
    },
    {
        "role": Role.STAFF,
        "name": "Demo Staff 3",
        "first_name": "Demo",
        "last_name": "Staff 3",
        "email": "demo.staff3@example.com",
        "username": "demo.staff3",
        "password": "St4ff!Prof#Demo3",
        "scopes": None,
        "inst_idx": 2,
        "employee_code": "EMP-STAFF-03",
        "designation": "Instructor",
        "department": "Information Technology",
    },
    # 5. STUDENT
    {
        "role": Role.STUDENT,
        "name": "Demo Student 1",
        "first_name": "Demo",
        "last_name": "Student 1",
        "email": "demo.student1@example.com",
        "username": "demo.student1",
        "password": "Stud3nt!Lms#Demo1",
        "scopes": None,
        "inst_idx": 0,
        "admission_number": "STU-DEMO-01",
        "program": "B.Tech",
        "branch": "Computer Science",
        "year_of_study": 3,
        "graduation_year": 2027,
    },
    {
        "role": Role.STUDENT,
        "name": "Demo Student 2",
        "first_name": "Demo",
        "last_name": "Student 2",
        "email": "demo.student2@example.com",
        "username": "demo.student2",
        "password": "Stud3nt!Lms#Demo2",
        "scopes": None,
        "inst_idx": 1,
        "admission_number": "STU-DEMO-02",
        "program": "B.Tech",
        "branch": "Electronics",
        "year_of_study": 2,
        "graduation_year": 2028,
    },
    {
        "role": Role.STUDENT,
        "name": "Demo Student 3",
        "first_name": "Demo",
        "last_name": "Student 3",
        "email": "demo.student3@example.com",
        "username": "demo.student3",
        "password": "Stud3nt!Lms#Demo3",
        "scopes": None,
        "inst_idx": 2,
        "admission_number": "STU-DEMO-03",
        "program": "B.Tech",
        "branch": "Information Technology",
        "year_of_study": 4,
        "graduation_year": 2026,
    },
]


async def ensure_demo_institutions(db, admin_user: User) -> list[Institution]:
    """Ensure at least 3 institutions exist for tenant isolation across the 3 demo sets."""
    result = await db.execute(select(Institution).where(Institution.deleted_at.is_(None)).order_by(Institution.created_at))
    institutions = list(result.scalars().all())

    # If fewer than 3 exist, create demo institution(s)
    default_demo_data = [
        {"name": "AI Smart Labs Solutions", "code": "GZTC", "email": "contact@gz-smartlabs.com"},
        {"name": "Charanteja Institute of Technology", "code": "GZTM", "email": "info@charanteja-inst.org"},
        {"name": "Demo Academy of Technology", "code": "DEMO3", "email": "admin@demoacademy.org"},
    ]

    while len(institutions) < 3:
        idx = len(institutions)
        data = default_demo_data[idx]
        new_inst = Institution(
            id=uuid7(),
            public_id=new_public_id(),
            name=data["name"],
            code=data["code"],
            org_type=OrganizationType.INSTITUTION.value,
            admin_id=admin_user.id,
            email=data["email"],
            phone="+919876543210",
            address_line1="Demo Campus Road",
            city="Hyderabad",
            state="Telangana",
            postal_code="500081",
            country="IN",
            timezone="Asia/Kolkata",
            status="active",
        )
        db.add(new_inst)
        await db.flush()
        institutions.append(new_inst)
        print(f"Created demo institution: {new_inst.name} ({new_inst.code})")

    return institutions


async def seed_demo_accounts(*, force: bool = False, output_file: str | None = None) -> dict[str, list[dict]]:
    settings = get_settings()

    # Safety check: Prevent running in production environments unless explicitly forced
    if settings.is_production_like and not force:
        print(
            f"ERROR: Cannot seed demo accounts in production-like environment ({settings.ENVIRONMENT}). "
            "Use --force to override if strictly intended for a test environment.",
            file=sys.stderr,
        )
        sys.exit(1)

    engine = build_engine(settings)
    report = {"created": [], "skipped": [], "failed": []}

    try:
        async with build_sessionmaker(engine)() as db:
            # 1. Check existing users
            existing_emails_res = await db.execute(select(User.email).where(User.email.is_not(None)))
            existing_emails = set(existing_emails_res.scalars().all())

            existing_usernames_res = await db.execute(select(User.username))
            existing_usernames = set(existing_usernames_res.scalars().all())

            # Find a super_admin or admin to be the admin_id for institutions
            admin_res = await db.execute(
                select(User).where(User.role.in_([Role.SUPER_ADMIN, Role.ADMIN]), User.status == UserStatus.ACTIVE).limit(1)
            )
            primary_admin = admin_res.scalar_one_or_none()

            institutions = await ensure_demo_institutions(db, primary_admin)
            now = utcnow()

            for item in DEMO_ACCOUNTS_DATA:
                email = item["email"]
                username = item["username"]
                role = item["role"]
                raw_password = item["password"]

                if email in existing_emails or username in existing_usernames:
                    report["skipped"].append({
                        "role": role.value if hasattr(role, "value") else str(role),
                        "email": email,
                        "username": username,
                        "reason": "Account already exists (preserved, not overwritten)",
                    })
                    continue

                try:
                    pwd_hash = await hash_password(raw_password)
                    user_id = uuid7()
                    inst_id = institutions[item["inst_idx"]].id if item.get("inst_idx") is not None else None

                    user = User(
                        id=user_id,
                        public_id=new_public_id(),
                        email=email,
                        username=username,
                        password_hash=pwd_hash,
                        first_name=item["first_name"],
                        last_name=item["last_name"],
                        phone="+919876543210",
                        role=role.value if hasattr(role, "value") else str(role),
                        status=UserStatus.ACTIVE.value,
                        institution_id=inst_id,
                        token_version=0,
                        must_change_password=False,
                        failed_login_attempts=0,
                        locked_until=None,
                        password_changed_at=now,
                        email_verified_at=now,
                    )
                    if item.get("scopes"):
                        user.scopes = item["scopes"]

                    user.profile = UserProfile(
                        user_id=user.id,
                        preferred_language=settings.DEFAULT_LANGUAGE,
                        timezone=settings.DEFAULT_TIMEZONE,
                    )

                    if role in (Role.INSTITUTION_HEAD, Role.STAFF):
                        user.employment = EmploymentProfile(
                            user_id=user.id,
                            institution_id=inst_id,
                            employee_code=item.get("employee_code"),
                            designation=item.get("designation"),
                            department=item.get("department"),
                            employment_type="full_time",
                            date_of_joining=date(2024, 1, 1),
                        )

                    if role == Role.STUDENT:
                        user.student = StudentProfile(
                            user_id=user.id,
                            institution_id=inst_id,
                            admission_number=item.get("admission_number"),
                            admission_date=date(2024, 8, 1),
                            program=item.get("program"),
                            branch=item.get("branch"),
                            year_of_study=item.get("year_of_study"),
                            graduation_year=item.get("graduation_year"),
                        )

                    db.add(user)
                    await db.flush()

                    existing_emails.add(email)
                    existing_usernames.add(username)

                    report["created"].append({
                        "role": role.value if hasattr(role, "value") else str(role),
                        "name": item["name"],
                        "email": email,
                        "username": username,
                        "password": raw_password,
                        "institution": institutions[item["inst_idx"]].name if item.get("inst_idx") is not None else "Global (N/A)",
                    })
                except Exception as exc:
                    report["failed"].append({
                        "role": role.value if hasattr(role, "value") else str(role),
                        "email": email,
                        "error": str(exc),
                    })

            await db.commit()
    finally:
        await engine.dispose()

    # Save credentials securely to a local file if specified or default
    cred_file = Path(output_file) if output_file else project_root / "var" / "demo_credentials.json"
    cred_file.parent.mkdir(parents=True, exist_ok=True)
    all_demo_info = [
        {
            "role": item["role"].value if hasattr(item["role"], "value") else str(item["role"]),
            "name": item["name"],
            "email": item["email"],
            "username": item["username"],
            "password": item["password"],
            "institution_idx": item.get("inst_idx"),
        }
        for item in DEMO_ACCOUNTS_DATA
    ]
    with open(cred_file, "w", encoding="utf-8") as f:
        json.dump(all_demo_info, f, indent=2)

    return report


def print_summary(report: dict[str, list[dict]]):
    print("\n" + "=" * 80)
    print("EXAMLMS DEMO ACCOUNTS SEED REPORT")
    print("=" * 80)
    print(f"Created: {len(report['created'])} | Skipped: {len(report['skipped'])} | Failed: {len(report['failed'])}")
    print("-" * 80)

    if report["created"]:
        print("\nCREATED ACCOUNTS:")
        for acc in report["created"]:
            print(f"[{acc['role']}] {acc['name']} ({acc['email']}) -> Password: {acc['password']} | Inst: {acc['institution']}")

    if report["skipped"]:
        print("\nSKIPPED ACCOUNTS (Already exist):")
        for acc in report["skipped"]:
            print(f"[{acc['role']}] {acc['email']} - {acc['reason']}")

    if report["failed"]:
        print("\nFAILED ACCOUNTS:")
        for acc in report["failed"]:
            print(f"[{acc['role']}] {acc['email']} - Error: {acc['error']}")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Seed 15 demo accounts for ExamLMS roles.")
    parser.add_argument("--force", action="store_true", help="Force execution even if environment looks production-like.")
    parser.add_argument("--output", type=str, default=None, help="Path to save demo credentials json file.")
    args = parser.parse_args()

    report = asyncio.run(seed_demo_accounts(force=args.force, output_file=args.output))
    print_summary(report)


if __name__ == "__main__":
    main()
