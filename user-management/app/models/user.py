import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String, false, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.ids import new_public_id
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.permissions.roles import UserStatus

if TYPE_CHECKING:
    from app.models.institution import Institution
    from app.models.profiles import EmploymentProfile, StudentGuardian, StudentProfile, UserProfile


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Account and identity. Personal, employment and student details live in 1:1 tables.

    ``id`` is the internal key used only for joins; ``public_id`` is the ``user_id`` the API exposes.
    Relationships use ``lazy="raise"``: every query must say what it loads (no hidden N+1 queries).
    """

    __tablename__ = "users"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, default=new_public_id)
    # Stored lower-cased. Optional for students only: they sign in with their username.
    email: Mapped[str | None] = mapped_column(String(254))
    username: Mapped[str] = mapped_column(String(50))  # stored lower-cased
    password_hash: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(50))
    middle_name: Mapped[str | None] = mapped_column(String(50))
    last_name: Mapped[str] = mapped_column(String(50))
    phone: Mapped[str | None] = mapped_column(String(20))  # E.164

    role: Mapped[str] = mapped_column(String(32))
    # Admins only: comma-wrapped list such as ",accounts.manage,careers.manage," (portable "contains" filter).
    scopes: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), default=UserStatus.ACTIVE, server_default=UserStatus.ACTIVE.value)
    status_reason: Mapped[str | None] = mapped_column(String(500))

    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="RESTRICT", use_alter=True)
    )
    manager_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    token_version: Mapped[int] = mapped_column(default=0, server_default="0")
    must_change_password: Mapped[bool] = mapped_column(default=False, server_default=false())
    failed_login_attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    locked_until: Mapped[datetime | None]
    last_login_at: Mapped[datetime | None]
    password_changed_at: Mapped[datetime | None]
    email_verified_at: Mapped[datetime | None]
    deleted_at: Mapped[datetime | None]

    institution: Mapped["Institution | None"] = relationship(foreign_keys=[institution_id], lazy="raise")
    manager: Mapped["User | None"] = relationship(foreign_keys=[manager_id], remote_side="User.id", lazy="raise")
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id], remote_side="User.id", lazy="raise")
    profile: Mapped["UserProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="raise", uselist=False
    )
    employment: Mapped["EmploymentProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="raise", uselist=False
    )
    student: Mapped["StudentProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="raise", uselist=False
    )
    guardians: Mapped[list["StudentGuardian"]] = relationship(
        back_populates="student", cascade="all, delete-orphan", lazy="raise", order_by="StudentGuardian.position"
    )

    __table_args__ = (
        # Uniqueness applies only to non-deleted users so identities can be reused later.
        Index(
            "uq_users_email_active",
            "email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_users_username_active",
            "username",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        # List screens: members of one institution by role, newest first (the most common query).
        Index(
            "ix_users_institution_role_created",
            "institution_id",
            "role",
            "created_at",
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        # Super-admin screens across all institutions (newest first, any role).
        Index(
            "ix_users_created_active",
            "created_at",
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_users_role_created",
            "role",
            "created_at",
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_users_manager_id", "manager_id", postgresql_where=text("manager_id IS NOT NULL")),
        Index("ix_users_created_by_id", "created_by_id", postgresql_where=text("created_by_id IS NOT NULL")),
        # "Contains" search stays fast on millions of rows (PostgreSQL pg_trgm; plain indexes elsewhere).
        *(
            Index(f"ix_users_{column}_trgm", column, postgresql_using="gin", postgresql_ops={column: "gin_trgm_ops"})
            for column in ("email", "username", "first_name", "last_name", "phone")
        ),
    )

    @property
    def scope_list(self) -> tuple[str, ...]:
        return tuple(scope for scope in (self.scopes or "").split(",") if scope)

    def set_scopes(self, scopes: list[str] | tuple[str, ...] | None) -> None:
        unique = sorted(set(scopes or ()))
        self.scopes = f",{','.join(unique)}," if unique else None

    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.first_name, self.middle_name, self.last_name) if part)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
