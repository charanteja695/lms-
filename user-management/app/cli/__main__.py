"""Operational commands.

    python -m app.cli create-super-admin --email ... --username ... --first-name ... --last-name ...
    python -m app.cli purge-expired

The password is read from the SUPER_ADMIN_PASSWORD environment variable or prompted for.
Super admins can only be created here, never through the HTTP API.
"""

import argparse
import asyncio
import getpass
import os
import sys

from pydantic import TypeAdapter, ValidationError

from app.cli.maintenance import purge_expired
from app.core.config import get_settings
from app.core.exceptions import ValidationFailedError
from app.core.ids import new_public_id
from app.core.password_policy import ensure_strong_password
from app.core.security import hash_password
from app.core.time import utcnow
from app.db.session import build_engine, build_sessionmaker
from app.db.types import uuid7
from app.models import User, UserProfile
from app.permissions.roles import Role, UserStatus
from app.repositories.user_repository import UserRepository
from app.schemas.types import EmailAddress, FirstName, LastName, Username


async def create_super_admin(args: argparse.Namespace) -> int:
    settings = get_settings()
    try:
        email = TypeAdapter(EmailAddress).validate_python(args.email)
        username = TypeAdapter(Username).validate_python(args.username)
        first_name = TypeAdapter(FirstName).validate_python(args.first_name)
        last_name = TypeAdapter(LastName).validate_python(args.last_name)
    except ValidationError as exc:
        print(f"Invalid input: {exc}", file=sys.stderr)
        return 2

    password = os.environ.get("SUPER_ADMIN_PASSWORD") or getpass.getpass("Password: ")
    if not os.environ.get("SUPER_ADMIN_PASSWORD") and getpass.getpass("Confirm password: ") != password:
        print("Passwords do not match", file=sys.stderr)
        return 2
    try:
        ensure_strong_password(password, min_length=settings.PASSWORD_MIN_LENGTH, email=email, username=username)
    except ValidationFailedError as exc:
        for detail in exc.details:
            print(f"- {detail['message']}", file=sys.stderr)
        return 2

    engine = build_engine(settings)
    try:
        async with build_sessionmaker(engine)() as db:
            users = UserRepository(db)
            if await users.email_taken(email) or await users.username_taken(username):
                print("A user with this email or username already exists", file=sys.stderr)
                return 1
            user = User(
                id=uuid7(),
                public_id=new_public_id(),
                email=email,
                username=username,
                password_hash=await hash_password(password),
                first_name=first_name,
                last_name=last_name,
                role=Role.SUPER_ADMIN,
                status=UserStatus.ACTIVE,
                token_version=0,
                must_change_password=False,
                failed_login_attempts=0,
                password_changed_at=utcnow(),
                email_verified_at=utcnow(),
            )
            user.profile = UserProfile(
                user_id=user.id,
                preferred_language=settings.DEFAULT_LANGUAGE,
                timezone=settings.DEFAULT_TIMEZONE,
            )
            user.employment = None
            user.student = None
            user.guardians = []
            db.add(user)
            await db.commit()
    finally:
        await engine.dispose()
    print(f"Super admin '{username}' created (user_id {user.public_id})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create-super-admin", help="Create the first (or another) super admin")
    create.add_argument("--email", required=True)
    create.add_argument("--username", required=True)
    create.add_argument("--first-name", required=True)
    create.add_argument("--last-name", required=True)

    purge = commands.add_parser("purge-expired", help="Delete expired sessions, tokens and old outbox events")
    purge.add_argument("--batch-size", type=int, default=5_000)

    args = parser.parse_args()
    if args.command == "create-super-admin":
        return asyncio.run(create_super_admin(args))
    if args.command == "purge-expired":
        totals = asyncio.run(purge_expired(get_settings(), batch_size=args.batch_size))
        for table, count in totals.items():
            print(f"{table}: {count} deleted")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
