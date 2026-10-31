import uuid
from typing import Any

from sqlalchemy import ColumnElement, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.attributes import set_committed_value

from app.models.profiles import EmploymentProfile, StudentProfile
from app.models.user import User
from app.utils.query import paginate

# Everything a full user response needs, loaded up front (relationships are lazy="raise").
USER_DETAIL_OPTIONS = (
    joinedload(User.institution),
    joinedload(User.manager),
    joinedload(User.created_by),
    selectinload(User.profile),
    selectinload(User.employment),
    selectinload(User.student),
    selectinload(User.guardians),
)
USER_LIST_OPTIONS = (
    joinedload(User.institution),
    selectinload(User.employment),
    selectinload(User.student),
)


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, user_id: uuid.UUID, *, include_deleted: bool = False) -> User | None:
        user = await self.db.get(User, user_id)
        if user is None or (user.deleted_at is not None and not include_deleted):
            return None
        return user

    async def get_by_public_id(
        self, public_id: int, *, include_deleted: bool = False, detailed: bool = False
    ) -> User | None:
        stmt = select(User).where(User.public_id == public_id)
        if detailed:
            stmt = stmt.options(*USER_DETAIL_OPTIONS).execution_options(populate_existing=True)
        user = (await self.db.execute(stmt)).unique().scalar_one_or_none()
        if user is None or (user.deleted_at is not None and not include_deleted):
            return None
        return user

    async def get_detailed(self, user_id: uuid.UUID) -> User:
        """Reload a user with everything a response needs, replacing any stale state in the session."""
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(*USER_DETAIL_OPTIONS)
            .execution_options(populate_existing=True)
        )
        return (await self.db.execute(stmt)).unique().scalar_one()

    async def get_by_identifier(self, identifier: str) -> User | None:
        """Look up a non-deleted user by email or username. Usernames cannot contain '@'."""
        value = identifier.strip().lower()
        column = User.email if "@" in value else User.username
        result = await self.db.execute(select(User).where(column == value, User.deleted_at.is_(None)))
        return result.scalar_one_or_none()

    async def email_taken(self, email: str, *, exclude_id: uuid.UUID | None = None) -> bool:
        return await self._exists(User.email == email.lower(), exclude_id)

    async def username_taken(self, username: str, *, exclude_id: uuid.UUID | None = None) -> bool:
        return await self._exists(User.username == username.lower(), exclude_id)

    async def _exists(self, condition: ColumnElement[bool], exclude_id: uuid.UUID | None) -> bool:
        conditions = [condition, User.deleted_at.is_(None)]
        if exclude_id is not None:
            conditions.append(User.id != exclude_id)
        return bool((await self.db.execute(select(exists().where(*conditions)))).scalar())

    async def employee_code_taken(
        self, code: str, institution_id: uuid.UUID | None, *, exclude_user_id: uuid.UUID | None
    ) -> bool:
        conditions = [
            EmploymentProfile.employee_code == code,
            EmploymentProfile.institution_id == institution_id
            if institution_id is not None
            else EmploymentProfile.institution_id.is_(None),
        ]
        if exclude_user_id is not None:
            conditions.append(EmploymentProfile.user_id != exclude_user_id)
        return bool((await self.db.execute(select(exists().where(*conditions)))).scalar())

    async def admission_number_taken(
        self, number: str, institution_id: uuid.UUID, *, exclude_user_id: uuid.UUID | None
    ) -> bool:
        conditions = [StudentProfile.admission_number == number, StudentProfile.institution_id == institution_id]
        if exclude_user_id is not None:
            conditions.append(StudentProfile.user_id != exclude_user_id)
        return bool((await self.db.execute(select(exists().where(*conditions)))).scalar())

    async def list(
        self,
        conditions: list[ColumnElement[bool]],
        *,
        order_by: list[Any],
        page: int,
        per_page: int,
    ) -> tuple[list[User], int, bool]:
        stmt = select(User).where(*conditions).order_by(*order_by)
        return await paginate(self.db, stmt, page, per_page, options=USER_LIST_OPTIONS)

    async def increment_failed_logins(self, user: User) -> int:
        """Atomic increment so parallel login attempts cannot under-count."""
        result = await self.db.execute(
            update(User)
            .where(User.id == user.id)
            .values(failed_login_attempts=User.failed_login_attempts + 1)
            .returning(User.failed_login_attempts)
            .execution_options(synchronize_session=False)
        )
        attempts = int(result.scalar_one())
        set_committed_value(user, "failed_login_attempts", attempts)
        return attempts

    async def bump_token_version_for_institution(self, institution_id: uuid.UUID) -> None:
        await self.db.execute(
            update(User)
            .where(User.institution_id == institution_id)
            .values(token_version=User.token_version + 1)
            .execution_options(synchronize_session="fetch")
        )

    async def clear_manager_references(self, manager_id: uuid.UUID) -> None:
        await self.db.execute(
            update(User)
            .where(User.manager_id == manager_id)
            .values(manager_id=None)
            .execution_options(synchronize_session="fetch")
        )

    def add(self, user: User) -> None:
        self.db.add(user)

    @staticmethod
    def event_payload(user: User, *, institution_public_id: int | None) -> dict[str, Any]:
        return {
            "user_id": str(user.public_id),
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "status": user.status,
            "organization_id": str(institution_public_id) if institution_public_id else None,
            "branch": user.student.branch if user.student else None,
            "graduation_year": user.student.graduation_year if user.student else None,
            "cgpa": float(user.student.cgpa) if (user.student and user.student.cgpa is not None) else None,
        }
