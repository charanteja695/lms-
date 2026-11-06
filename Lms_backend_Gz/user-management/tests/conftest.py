import os

# Must be set before any app module reads settings.
os.environ.update(
    {
        "ENVIRONMENT": "test",
        # Fast in-memory SQLite by default; set TEST_DATABASE_URL to run against PostgreSQL.
        "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite://"),
        "REDIS_URL": "redis://localhost:6379/15",
        "JWT_ALGORITHM": "HS256",
        "JWT_SECRET_KEY": "test-jwt-secret-key-that-is-long-enough-0123456789",
        "TOKEN_HASH_SECRET": "test-token-hash-secret-that-is-long-enough-012345",
        "ARGON2_TIME_COST": "1",
        "ARGON2_MEMORY_COST_KIB": "1024",
        "ARGON2_PARALLELISM": "1",
        "LOG_JSON": "false",
        "LOG_LEVEL": "ERROR",
        "EMAIL_BACKEND": "console",
        "RATE_LIMIT_ENABLED": "true",
        "LOGIN_RATE_LIMIT_PER_MINUTE": "1000",
        "REFRESH_RATE_LIMIT_PER_MINUTE": "1000",
        "FORGOT_PASSWORD_RATE_LIMIT_PER_HOUR": "1000",
        "FORGOT_PASSWORD_IDENTIFIER_RATE_LIMIT_PER_HOUR": "1000",
        "OTP_VERIFY_RATE_LIMIT_PER_MINUTE": "1000",
        "RESET_PASSWORD_RATE_LIMIT_PER_MINUTE": "1000",
        "MFA_REQUIRED_ROLES": "[]",
        "REFRESH_COOKIE_SECURE": "false",
        "MFA_VERIFY_RATE_LIMIT_PER_MINUTE": "1000",
        "IMPORT_RATE_LIMIT_PER_HOUR": "1000",
        "EXPORT_RATE_LIMIT_PER_HOUR": "1000",
    }
)

import re  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from typing import Any  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from fakeredis import FakeAsyncRedis  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.ids import new_public_id  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.core.time import utcnow  # noqa: E402
from app.db.session import build_engine, build_sessionmaker  # noqa: E402
from app.db.types import uuid7  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, User, UserProfile  # noqa: E402
from app.notifications.email import EmailMessage  # noqa: E402
from app.permissions.roles import Role, UserStatus  # noqa: E402

API = "/api/v1"
STRONG_PASSWORD = "Str0ng!Passphrase#1"
NEW_PASSWORD = "An0ther!Passphrase#2"
SUPER_ADMIN_EMAIL = "platform.owner@example.com"
SUPER_ADMIN_USERNAME = "platform.owner"

ADDRESS = {
    "line1": "Plot 42, Road No. 5",
    "line2": "Jubilee Hills",
    "city": "Hyderabad",
    "state": "Telangana",
    "postal_code": "500033",
    "country": "IN",
}


@dataclass
class CapturingEmailSender:
    messages: list[EmailMessage] = field(default_factory=list)

    async def send(self, message: EmailMessage) -> None:
        self.messages.append(message)

    def last_to(self, to: str) -> EmailMessage:
        return next(m for m in reversed(self.messages) if m.to == to)

    def otp_for(self, to: str) -> str:
        match = re.search(r"one-time code is: (\d+)", self.last_to(to).text_body)
        assert match, "no OTP in email"
        return match.group(1)

    def link_token_for(self, to: str) -> str:
        match = re.search(r"\?token=([A-Za-z0-9_-]+)", self.last_to(to).text_body)
        assert match, "no link token in email"
        return match.group(1)


@pytest_asyncio.fixture
async def app() -> AsyncIterator[FastAPI]:
    settings = get_settings()
    application = create_app(settings)
    engine = build_engine(settings)
    async with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            available = await conn.exec_driver_sql("SELECT 1 FROM pg_available_extensions WHERE name = 'pg_trgm'")
            if available.scalar():
                await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pg_trgm")
            else:  # e.g. minimal local builds: create the schema without trigram search indexes
                for table in Base.metadata.tables.values():
                    for index in [i for i in table.indexes if i.name and i.name.endswith("_trgm")]:
                        table.indexes.discard(index)
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    application.state.engine = engine
    application.state.sessionmaker = build_sessionmaker(engine)
    application.state.redis = FakeAsyncRedis(decode_responses=True)
    application.state.email_sender = CapturingEmailSender()
    yield application
    await application.state.redis.aclose()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        yield http


@pytest.fixture
def emails(app: FastAPI) -> CapturingEmailSender:
    return app.state.email_sender


@pytest_asyncio.fixture
async def super_admin(app: FastAPI) -> User:
    async with app.state.sessionmaker() as db:
        user = User(
            id=uuid7(),
            public_id=new_public_id(),
            email=SUPER_ADMIN_EMAIL,
            username=SUPER_ADMIN_USERNAME,
            password_hash=await hash_password(STRONG_PASSWORD),
            first_name="Platform",
            last_name="Owner",
            role=Role.SUPER_ADMIN,
            status=UserStatus.ACTIVE,
            token_version=0,
            must_change_password=False,
            failed_login_attempts=0,
            password_changed_at=utcnow(),
        )
        user.profile = UserProfile(user_id=user.id, preferred_language="en", timezone="Asia/Kolkata")
        user.employment = None
        user.student = None
        user.guardians = []
        db.add(user)
        await db.commit()
        return user


# ------------------------------------------------------------------ helpers


async def login(client: AsyncClient, identifier: str, password: str = STRONG_PASSWORD) -> dict[str, Any]:
    response = await client.post(f"{API}/auth/login", json={"identifier": identifier, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def bearer(login_response: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {login_response['token']['access_token']}"}


async def activate_account(
    client: AsyncClient, identifier: str, temp_password: str = STRONG_PASSWORD
) -> dict[str, str]:
    """Log in with a temporary password, change it, log in again. Returns auth headers."""
    body = await login(client, identifier, temp_password)
    assert body["user"]["must_change_password"] is True
    response = await client.post(
        f"{API}/auth/change-password",
        json={"current_password": temp_password, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
        headers=bearer(body),
    )
    assert response.status_code == 200, response.text
    return bearer(await login(client, identifier, NEW_PASSWORD))


_phone_counter = iter(range(10_000_000))


def unique_phone() -> str:
    return f"+9198{next(_phone_counter):08d}"


def _name(username: str) -> str:
    return re.sub(r"[^A-Za-z]+", " ", username).strip().title()


def staff_payload(username: str, *, role: str = "staff", **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "role": role,
        "account": {"email": f"{username}@example.com", "username": username, "password": STRONG_PASSWORD},
        "personal_info": {"first_name": _name(username), "last_name": "Test", "phone": unique_phone()},
        "employment": {"employee_code": f"EMP-{username.upper().replace('.', '-')}", "designation": "Teacher"},
    }
    payload.update(overrides)
    return payload


def student_payload(username: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "role": "student",
        "account": {"email": f"{username}@example.com", "username": username, "password": STRONG_PASSWORD},
        "personal_info": {"first_name": _name(username), "last_name": "Test", "date_of_birth": "2012-04-15"},
        "student": {
            "admission_number": f"ADM/{username.upper().replace('.', '-')}",
            "guardians": [{"full_name": "Suresh Test", "relationship": "father", "phone": unique_phone()}],
        },
    }
    payload.update(overrides)
    return payload


def admin_payload(username: str) -> dict[str, Any]:
    return {
        "account": {"email": f"{username}@example.com", "username": username, "password": STRONG_PASSWORD},
        "personal_info": {"first_name": _name(username), "last_name": "Admin", "phone": unique_phone()},
    }


def institution_payload(code: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": f"{code} Public School",
        "code": code,
        "type": "school",
        "contact": {"email": f"office.{code.lower()}@example.com", "phone": unique_phone()},
        "address": ADDRESS,
    }
    payload.update(overrides)
    return payload


async def create_user(client: AsyncClient, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(f"{API}/users", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["user"]


@pytest_asyncio.fixture
async def root_headers(client: AsyncClient, super_admin: User) -> dict[str, str]:
    return bearer(await login(client, SUPER_ADMIN_EMAIL))


@dataclass
class Hierarchy:
    root: dict[str, str]
    admin: dict[str, str]
    admin_id: str
    organization_id: str
    head: dict[str, str]
    head_id: str
    staff: dict[str, str]
    staff_id: str
    student: dict[str, str]
    student_id: str


@pytest_asyncio.fixture
async def hierarchy(client: AsyncClient, root_headers: dict[str, str]) -> Hierarchy:
    """Super Admin -> Admin -> Institution -> Head -> Staff -> Student, each created by its parent."""
    response = await client.post(f"{API}/admins", json=admin_payload("admin1"), headers=root_headers)
    assert response.status_code == 201, response.text
    admin_id = response.json()["admin"]["user_id"]
    admin = await activate_account(client, "admin1")

    response = await client.post(f"{API}/institutions", json=institution_payload("SPH-01"), headers=admin)
    assert response.status_code == 201, response.text
    organization_id = response.json()["institution"]["organization_id"]

    head_user = await create_user(
        client, admin, staff_payload("head1", role="institution_head", organization_id=organization_id)
    )
    head = await activate_account(client, "head1")
    staff_user = await create_user(client, head, staff_payload("staff1"))
    staff = await activate_account(client, "staff1")
    student_user = await create_user(client, staff, student_payload("student1"))
    student = await activate_account(client, "student1")

    return Hierarchy(
        root=root_headers,
        admin=admin,
        admin_id=admin_id,
        organization_id=organization_id,
        head=head,
        head_id=head_user["user_id"],
        staff=staff,
        staff_id=staff_user["user_id"],
        student=student,
        student_id=student_user["user_id"],
    )
