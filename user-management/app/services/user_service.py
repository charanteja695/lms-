"""User management across the hierarchy: super admin -> admin -> institution head -> staff -> student.

Every operation addresses users by their public ``user_id`` and runs, in order:
role permission -> institution scope -> resource scope -> data rules -> uniqueness -> write.
"""

import re
import secrets
import unicodedata
import uuid
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import timedelta
from typing import Any

from sqlalchemy import ColumnElement, func, inspect, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstanceState

from app.core.config import Settings
from app.core.context import RequestContext
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.password_policy import ensure_strong_password
from app.core.security import generate_secure_token, generate_temporary_password, hash_password, hash_token
from app.core.time import start_of_day, utcnow
from app.db.session import commit_or_conflict
from app.db.types import uuid7
from app.domain.enums import SortOrder
from app.models.institution import Institution
from app.models.password_reset import PasswordResetPurpose, PasswordResetRequest
from app.models.profiles import EmploymentProfile, StudentGuardian, StudentProfile, UserProfile
from app.models.user import User
from app.notifications.notifier import Notifier
from app.permissions import policies
from app.permissions.policies import Action
from app.permissions.roles import (
    DEFAULT_ADMIN_SCOPES,
    SCOPE_FOR_ORGANIZATION,
    InstitutionStatus,
    Role,
    StatusChange,
    UserStatus,
    organization_type_for,
)
from app.repositories.institution_repository import InstitutionRepository
from app.repositories.password_reset_repository import PasswordResetRepository
from app.repositories.user_repository import UserRepository
from app.schemas.types import RESERVED_USERNAMES
from app.schemas.user import (
    AddressInput,
    GuardianInput,
    MyProfileUpdate,
    PersonalInfoUpdate,
    UserCreate,
    UserFilters,
    UserListQuery,
    UserSortColumn,
    UserUpdate,
)
from app.services.audit_service import AuditAction, AuditService
from app.services.mfa_service import MfaService
from app.services.session_service import RevokeReason, SessionService
from app.utils.query import LIKE_ESCAPE, contains_pattern
from app.validators.user_rules import user_record_problems

_SORT_COLUMNS = {
    UserSortColumn.CREATED_TIME: User.created_at,
    UserSortColumn.FIRST_NAME: User.first_name,
    UserSortColumn.LAST_NAME: User.last_name,
    UserSortColumn.EMAIL: User.email,
    UserSortColumn.LAST_LOGIN_TIME: User.last_login_at,
}
_ACTION_VERBS = {
    Action.VIEW: "view",
    Action.CREATE: "create",
    Action.UPDATE: "update",
    Action.CHANGE_STATUS: "change the status of",
    Action.DELETE: "delete",
    Action.REVOKE: "revoke access for",
}
_PROFILE_FIELDS = ("gender", "date_of_birth", "alternate_phone", "preferred_language", "timezone")
_USER_NAME_FIELDS = ("first_name", "middle_name", "last_name", "phone")
_ROLE_LABELS = {
    Role.EMPLOYER_ADMIN: "employer admin",
    Role.RECRUITER: "recruiter",
    Role.ADMIN: "admin",
    Role.INSTITUTION_HEAD: "institution head",
    Role.STAFF: "staff",
    Role.STUDENT: "student",
    Role.SUPER_ADMIN: "super admin",
}


def _detail(field: str, code: str, message: str) -> dict[str, str]:
    return {"field": field, "code": code, "message": message}


UNUSABLE_PASSWORD_PREFIX = "!"


@dataclass
class PreparedUser:
    user: User
    institution: Institution | None
    password: str | None
    password_generated: bool = False


@dataclass
class ReservedIdentities:
    """Identities claimed by earlier rows of one bulk import (not yet in the database)."""

    emails: set[str] = dataclass_field(default_factory=set)
    usernames: set[str] = dataclass_field(default_factory=set)
    employee_codes: set[tuple[object, str]] = dataclass_field(default_factory=set)
    admission_numbers: set[tuple[object, str]] = dataclass_field(default_factory=set)

    def check(self, user: User) -> None:
        details = []
        code = user.employment.employee_code if user.employment else None
        number = user.student.admission_number if user.student else None
        if user.email and user.email in self.emails:
            details.append(_detail("account.email", "DUPLICATE_IN_FILE", "This email appears earlier in the file"))
        if user.username in self.usernames:
            details.append(
                _detail("account.username", "DUPLICATE_IN_FILE", "This username appears earlier in the file")
            )
        if code and (user.institution_id, code) in self.employee_codes:
            details.append(
                _detail(
                    "employment.employee_code", "DUPLICATE_IN_FILE", "This employee code appears earlier in the file"
                )
            )
        if number and (user.institution_id, number) in self.admission_numbers:
            details.append(
                _detail(
                    "student.admission_number", "DUPLICATE_IN_FILE", "This admission number appears earlier in the file"
                )
            )
        if details:
            raise ConflictError("Some details are repeated in the file.", details=details)

    def claim(self, user: User) -> None:
        if user.email:
            self.emails.add(user.email)
        self.usernames.add(user.username)
        if user.employment and user.employment.employee_code:
            self.employee_codes.add((user.institution_id, user.employment.employee_code))
        if user.student:
            self.admission_numbers.add((user.institution_id, user.student.admission_number))


class UserService:
    def __init__(self, db: AsyncSession, settings: Settings, ctx: RequestContext, notifier: Notifier) -> None:
        self.db = db
        self.settings = settings
        self.notifier = notifier
        self.users = UserRepository(db)
        self.institutions = InstitutionRepository(db)
        self.resets = PasswordResetRepository(db)
        self.sessions = SessionService(db, settings)
        self.audit = AuditService(db, ctx)
        self._institution_cache: dict[int, Institution] = {}

    # ================================================================== queries

    async def list_users(
        self, actor: User, query: UserListQuery, *, only_role: Role | None = None
    ) -> tuple[list[User], int, bool]:
        conditions = await self.filter_conditions(actor, query, only_role=only_role)
        if conditions is None:
            return [], 0, True
        column = _SORT_COLUMNS[query.sort_column]
        descending = query.sort_order == SortOrder.DESC
        ordered = column.desc() if descending else column.asc()
        if query.sort_column == UserSortColumn.LAST_LOGIN_TIME:  # the only nullable sort column
            ordered = ordered.nulls_last()
        # A plain ORDER BY in one direction lets PostgreSQL walk the matching index instead of sorting.
        tiebreaker = User.id.desc() if descending else User.id.asc()
        return await self.users.list(
            conditions, order_by=[ordered, tiebreaker], page=query.page, per_page=query.per_page
        )

    async def prepare_export(
        self, actor: User, query: UserFilters, *, only_role: Role | None = None
    ) -> list[ColumnElement[bool]] | None:
        """Authorise an export and record it in the audit log. Rows are streamed by the caller."""
        conditions = await self.filter_conditions(actor, query, only_role=only_role)
        self.audit.log(
            AuditAction.USERS_EXPORTED,
            actor_id=actor.id,
            resource_type="user",
            institution_id=actor.institution_id,
            details={"filters": query.model_dump(mode="json", exclude_none=True), "only_role": only_role},
        )
        await self.db.commit()
        return conditions

    async def filter_conditions(
        self, actor: User, query: UserFilters, *, only_role: Role | None = None
    ) -> list[ColumnElement[bool]] | None:
        """WHERE conditions for everything ``actor`` may see that matches ``query``.
        ``None`` means nothing can match (e.g. an unknown organization_id)."""
        viewable = policies.allowed_target_roles(actor.role, Action.VIEW)
        if not viewable:
            raise PermissionDeniedError("You are not allowed to view other users.")

        query_role = getattr(query, "role", None)
        requested = only_role or (Role(query_role.value) if query_role else None)
        if requested is not None and requested not in viewable:
            raise PermissionDeniedError(f"You are not allowed to view {_ROLE_LABELS[requested]} accounts.")
        roles = {requested} if requested else set(viewable)

        conditions: list[ColumnElement[bool]] = [User.role.in_(roles), User.id != actor.id]
        if query.status == UserStatus.DELETED:
            if actor.role != Role.SUPER_ADMIN:
                raise PermissionDeniedError("Only super admins can view deleted users.")
            conditions.append(User.deleted_at.is_not(None))
        else:
            conditions.append(User.deleted_at.is_(None))
            if query.status is not None:
                conditions.append(User.status == query.status)

        conditions.extend(self._scope_conditions(actor))

        for field, column in (
            ("organization_id", None),
            ("manager_user_id", User.manager_id),
            ("created_by_user_id", User.created_by_id),
        ):
            public_id = getattr(query, field, None)
            if public_id is None:
                continue
            if column is None:
                institution = await self.institutions.get_by_public_id(public_id, include_deleted=True)
                if institution is None:
                    return None
                conditions.append(User.institution_id == institution.id)
            else:
                referenced = await self.users.get_by_public_id(public_id, include_deleted=True)
                if referenced is None:
                    return None
                conditions.append(column == referenced.id)

        gender = getattr(query, "gender", None)
        if gender:
            conditions.append(User.profile.has(UserProfile.gender == gender))
        department = getattr(query, "department", None)
        if department:
            conditions.append(User.employment.has(func.lower(EmploymentProfile.department) == department.lower()))
        employment_type = getattr(query, "employment_type", None)
        if employment_type:
            conditions.append(User.employment.has(EmploymentProfile.employment_type == employment_type))
        for field, text_column in (
            ("program", StudentProfile.program),
            ("branch", StudentProfile.branch),
            ("section", StudentProfile.section),
        ):
            value = getattr(query, field, None)
            if value:
                conditions.append(User.student.has(func.lower(text_column) == value.lower()))
        for field, int_column in (
            ("year_of_study", StudentProfile.year_of_study),
            ("graduation_year", StudentProfile.graduation_year),
        ):
            value = getattr(query, field, None)
            if value is not None:
                conditions.append(User.student.has(int_column == value))
        scope = getattr(query, "scope", None)
        if scope:
            conditions.append(User.scopes.like(f"%,{scope},%"))
        if query.email_verified is not None:
            conditions.append(
                User.email_verified_at.is_not(None) if query.email_verified else User.email_verified_at.is_(None)
            )
        if query.created_from:
            conditions.append(User.created_at >= start_of_day(query.created_from))
        if query.created_to:
            conditions.append(User.created_at < start_of_day(query.created_to + timedelta(days=1)))

        if query.search_text:
            pattern = contains_pattern(query.search_text.lower())

            def matches(column: Any) -> ColumnElement[bool]:
                return column.ilike(pattern, escape=LIKE_ESCAPE)  # type: ignore[no-any-return]

            conditions.append(
                or_(
                    matches(User.email),
                    matches(User.username),
                    matches(User.first_name),
                    matches(User.last_name),
                    matches(User.phone),
                    User.employment.has(matches(EmploymentProfile.employee_code)),
                    User.student.has(matches(StudentProfile.admission_number)),
                )
            )
        return conditions

    def _scope_conditions(self, actor: User) -> list[ColumnElement[bool]]:
        if actor.role == Role.SUPER_ADMIN:
            return []
        if actor.role == Role.ADMIN:
            return [User.institution_id.in_(self.institutions.ids_owned_by_admin(actor.id))]
        return [User.institution_id == actor.institution_id]

    async def get_user(self, actor: User, user_id: int, *, expected_role: Role | None = None) -> User:
        return await self._load_target(actor, user_id, Action.VIEW, expected_role)

    async def get_me(self, actor: User) -> User:
        return await self.users.get_detailed(actor.id)

    # ================================================================== create

    async def create_user(self, actor: User, data: UserCreate) -> tuple[User, "PreparedUser"]:
        prepared = await self.prepare_user(actor, data)
        try:
            setup_token = await self.persist_user(actor, prepared)
        except IntegrityError as exc:
            await self.db.rollback()
            raise ConflictError("Some details are already used by another record.") from exc
        await commit_or_conflict(self.db, "Some details are already used by another record.")
        self.notify_created(prepared.user, setup_token)
        return await self.users.get_detailed(prepared.user.id), prepared

    async def prepare_user(
        self, actor: User, data: UserCreate, *, reserved: "ReservedIdentities | None" = None
    ) -> "PreparedUser":
        """Run every permission, data and uniqueness rule for a new user without writing anything.

        ``reserved`` holds identities already claimed by earlier rows of the same bulk import.
        """
        role = Role(data.role)
        if not policies.can_act_on_role(actor.role, Action.CREATE, role):
            raise PermissionDeniedError(f"You are not allowed to create {_ROLE_LABELS[role]} accounts.")

        institution = await self._resolve_institution(actor, role, data.organization_id, require_active=True)
        manager = await self._resolve_manager(
            actor, role, institution, data.manager_user_id, use_default="manager_user_id" not in data.model_fields_set
        )

        info = data.personal_info
        now = utcnow()
        user = User(
            id=uuid7(),
            public_id=new_public_id(),
            email=data.account.email,
            username=data.account.username
            or await self._generate_username(
                info.first_name, info.last_name, avoid=reserved.usernames if reserved else frozenset()
            ),
            password_hash="",
            first_name=info.first_name,
            middle_name=info.middle_name,
            last_name=info.last_name,
            phone=info.phone,
            role=role,
            status=UserStatus.ACTIVE,
            institution_id=institution.id if institution else None,
            manager_id=manager.id if manager else None,
            created_by_id=actor.id,
            token_version=0,
            must_change_password=True,
            failed_login_attempts=0,
            password_changed_at=now,
        )
        user.profile = UserProfile(
            user_id=user.id,
            gender=info.gender,
            date_of_birth=info.date_of_birth,
            alternate_phone=info.alternate_phone,
            preferred_language=info.preferred_language or self.settings.DEFAULT_LANGUAGE,
            timezone=info.timezone or (institution.timezone if institution else self.settings.DEFAULT_TIMEZONE),
        )
        _apply_address(user.profile, data.address)
        user.employment = (
            EmploymentProfile(user_id=user.id, institution_id=user.institution_id, **data.employment.model_dump())
            if data.employment
            else None
        )
        if data.student:
            user.student = StudentProfile(
                user_id=user.id,
                institution_id=user.institution_id,
                **data.student.model_dump(exclude={"guardians"}),
            )
            user.guardians = _build_guardians(user.id, data.student.guardians)
        else:
            user.student = None
            user.guardians = []

        if role == Role.ADMIN:
            scopes = data.scopes if data.scopes is not None else DEFAULT_ADMIN_SCOPES
            user.set_scopes([scope.value for scope in scopes])
        elif data.scopes:
            raise ValidationFailedError(details=[_detail("scopes", "NOT_ALLOWED", "Only admins have scopes")])
        self._raise_if_invalid(user)
        if reserved is not None:
            reserved.check(user)
        await self._ensure_unique(
            user,
            exclude_id=None,
            email=True,
            username=data.account.username is not None,
            employee_code=True,
            admission_number=True,
        )

        password, generated = data.account.password, False
        if password is not None:
            ensure_strong_password(
                password,
                min_length=self.settings.PASSWORD_MIN_LENGTH,
                email=user.email,
                username=user.username,
                field="account.password",
            )
        elif user.email is None:
            # No email to send a set-up link to: generate a temporary password, shown once to the creator.
            password, generated = generate_temporary_password(self.settings.PASSWORD_MIN_LENGTH), True
        if reserved is not None:
            reserved.claim(user)
        return PreparedUser(user=user, institution=institution, password=password, password_generated=generated)

    async def persist_user(self, actor: User, prepared: "PreparedUser") -> str | None:
        """Stage a prepared user in the current transaction. Returns the account set-up token, if any."""
        user, institution, now = prepared.user, prepared.institution, utcnow()
        if prepared.password is not None:
            user.password_hash = await hash_password(prepared.password)
        else:
            # Nobody can log in with this marker; the user sets a real password through the emailed link.
            user.password_hash = UNUSABLE_PASSWORD_PREFIX + generate_secure_token(24)

        self.users.add(user)
        setup_token: str | None = None
        if prepared.password is None:
            await self.db.flush()  # the set-up request references the new user row
            setup_token = generate_secure_token()
            self.resets.add(
                PasswordResetRequest(
                    id=uuid7(),
                    user_id=user.id,
                    purpose=PasswordResetPurpose.ACCOUNT_SETUP,
                    link_token_hash=hash_token(setup_token),
                    expires_at=now + timedelta(hours=self.settings.ACCOUNT_SETUP_EXPIRE_HOURS),
                )
            )

        self.audit.log(
            AuditAction.USER_CREATED,
            actor_id=actor.id,
            resource_type="user",
            resource_id=user.id,
            institution_id=user.institution_id,
            details={"role": user.role, "account_setup_link_sent": setup_token is not None},
        )
        self._event("user.created", user, institution)
        return setup_token

    def notify_created(self, user: User, setup_token: str | None) -> None:
        if setup_token is not None:
            self.notifier.account_setup(user, link_token=setup_token)
        else:
            self.notifier.account_created(user)

    # ================================================================== update

    async def update_user(
        self, actor: User, user_id: int, data: UserUpdate, *, expected_role: Role | None = None
    ) -> User:
        target = await self._load_target(actor, user_id, Action.UPDATE, expected_role)
        existing_problems = self._problem_keys(target)
        fields = data.model_fields_set
        before = _identity_snapshot(target)

        # --- role (only institution_head <-> staff)
        new_role = Role(target.role)
        if data.role is not None and Role(data.role) != new_role:
            requested = Role(data.role)
            if {new_role, requested} - {Role.INSTITUTION_HEAD, Role.STAFF}:
                raise ValidationFailedError(
                    "This role change is not supported.",
                    code="ROLE_CHANGE_NOT_ALLOWED",
                    details=[
                        _detail(
                            "role",
                            "ROLE_CHANGE_NOT_ALLOWED",
                            "Role can only change between institution_head and staff. Create a new account instead.",
                        )
                    ],
                )
            if not policies.can_act_on_role(actor.role, Action.UPDATE, requested):
                raise PermissionDeniedError(f"You are not allowed to assign the {_ROLE_LABELS[requested]} role.")
            new_role = requested

        # --- institution
        institution = target.institution
        if "organization_id" in fields:
            if data.organization_id is None:
                if policies.is_organization_scoped(new_role):
                    raise ValidationFailedError(
                        details=[_detail("organization_id", "REQUIRED", "This user must belong to an institution")]
                    )
            elif institution is None or data.organization_id != institution.public_id:
                institution = await self._resolve_institution(
                    actor, new_role, data.organization_id, require_active=True
                )
        new_institution_id = institution.id if institution else None
        hierarchy_changed = new_role != target.role or new_institution_id != target.institution_id

        # --- manager
        if "manager_user_id" in fields:
            if data.manager_user_id == target.public_id:
                raise ValidationFailedError(
                    details=[_detail("manager_user_id", "INVALID_MANAGER", "A user cannot be their own manager")]
                )
            manager = await self._resolve_manager(actor, new_role, institution, data.manager_user_id, use_default=False)
            target.manager_id = manager.id if manager else None
        elif hierarchy_changed:
            target.manager_id = None

        target.role = new_role
        target.institution_id = new_institution_id

        # --- admin scopes
        scopes_changed = False
        if "scopes" in fields and data.scopes is not None:
            if new_role != Role.ADMIN:
                raise ValidationFailedError(details=[_detail("scopes", "NOT_ALLOWED", "Only admins have scopes")])
            if set(data.scopes) != set(target.scope_list):
                await self._ensure_scopes_keep_ownership(target, [scope.value for scope in data.scopes])
                target.set_scopes([scope.value for scope in data.scopes])
                scopes_changed = True

        # --- sections
        if data.account is not None:
            account_fields = data.account.model_fields_set
            if "email" in account_fields and data.account.email and data.account.email != target.email:
                target.email = data.account.email
                target.email_verified_at = None
            if "username" in account_fields and data.account.username:
                target.username = data.account.username
        if data.personal_info is not None:
            self._apply_personal_info(target, data.personal_info)
        if "address" in fields:
            _apply_address(self._profile_of(target), data.address)
        if "employment" in fields:
            if data.employment is None:
                target.employment = None
            else:
                employment = target.employment or EmploymentProfile(user_id=target.id)
                for name in data.employment.model_fields_set:
                    setattr(employment, name, getattr(data.employment, name))
                target.employment = employment
        if data.student is not None:
            student_fields = data.student.model_fields_set
            if target.student is None:
                if not data.student.admission_number:
                    raise ValidationFailedError(
                        details=[_detail("student.admission_number", "REQUIRED", "Admission number is required")]
                    )
                target.student = StudentProfile(user_id=target.id, admission_number=data.student.admission_number)
            if "admission_number" in student_fields and data.student.admission_number:
                target.student.admission_number = data.student.admission_number
            for name in student_fields - {"admission_number", "guardians"}:
                setattr(target.student, name, getattr(data.student, name))
            if "guardians" in student_fields and data.student.guardians is not None:
                target.guardians = _build_guardians(target.id, data.student.guardians)

        # Keep the per-institution copies used for uniqueness in sync.
        if target.employment is not None:
            target.employment.institution_id = target.institution_id
        if target.student is not None and target.institution_id is not None:
            target.student.institution_id = target.institution_id

        self._raise_if_invalid(target, ignore=existing_problems)
        after = _identity_snapshot(target)
        await self._ensure_unique(
            target,
            exclude_id=target.id,
            email=after["email"] != before["email"],
            username=after["username"] != before["username"],
            employee_code=after["employee_code"] != before["employee_code"] or hierarchy_changed,
            admission_number=after["admission_number"] != before["admission_number"] or hierarchy_changed,
        )

        changed_fields = _changed_fields(target)
        if not changed_fields:
            return target

        if hierarchy_changed:
            # Role and institution are embedded in access tokens and define who reports to whom.
            await self.users.clear_manager_references(target.id)
            await self.sessions.revoke_all_for_user(target, reason=RevokeReason.ROLE_CHANGED)
        elif scopes_changed:  # scopes are embedded in access tokens too
            await self.sessions.revoke_all_for_user(target, reason=RevokeReason.ROLE_CHANGED)

        self.audit.log(
            AuditAction.USER_UPDATED,
            actor_id=actor.id,
            resource_type="user",
            resource_id=target.id,
            institution_id=target.institution_id,
            details={"changed_fields": changed_fields},
        )
        self._event("user.updated", target, institution)
        await commit_or_conflict(self.db, "Some details are already used by another record.")
        return await self.users.get_detailed(target.id)

    async def set_password(
        self, actor: User, user_id: int, new_password: str, *, expected_role: Role | None = None
    ) -> None:
        """A manager sets a temporary password (e.g. for students without email). The user must change it
        at next sign-in, and every existing session ends."""
        target = await self._load_target(actor, user_id, Action.UPDATE, expected_role)
        ensure_strong_password(
            new_password,
            min_length=self.settings.PASSWORD_MIN_LENGTH,
            email=target.email,
            username=target.username,
            field="new_password",
        )
        target.password_hash = await hash_password(new_password)
        target.must_change_password = True
        target.password_changed_at = utcnow()
        target.failed_login_attempts = 0
        target.locked_until = None
        await self.resets.consume_all_open(target.id, now=utcnow())
        await self.sessions.revoke_all_for_user(target, reason=RevokeReason.PASSWORD_SET_BY_MANAGER)
        self.audit.log(
            AuditAction.USER_PASSWORD_SET,
            actor_id=actor.id,
            resource_type="user",
            resource_id=target.id,
            institution_id=target.institution_id,
        )
        await self.db.commit()
        self.notifier.password_changed(target)

    async def update_my_profile(self, actor: User, data: MyProfileUpdate) -> User:
        user = await self.users.get_detailed(actor.id)
        existing_problems = self._problem_keys(user)
        if data.personal_info is not None:
            self._apply_personal_info(user, data.personal_info)
        if "address" in data.model_fields_set:
            _apply_address(self._profile_of(user), data.address)
        self._raise_if_invalid(user, ignore=existing_problems)

        changed_fields = _changed_fields(user)
        if not changed_fields:
            return user
        self.audit.log(
            AuditAction.USER_UPDATED,
            actor_id=user.id,
            resource_type="user",
            resource_id=user.id,
            institution_id=user.institution_id,
            details={"changed_fields": changed_fields, "self_service": True},
        )
        self._event("user.updated", user, user.institution)
        await self.db.commit()
        return await self.users.get_detailed(user.id)

    # ================================================================== status / delete / revoke

    async def change_status(
        self,
        actor: User,
        user_id: int,
        status: StatusChange,
        reason: str | None,
        *,
        expected_role: Role | None = None,
    ) -> User:
        target = await self._load_target(actor, user_id, Action.CHANGE_STATUS, expected_role)
        if target.status == status:
            return target

        previous = target.status
        target.status = status
        target.status_reason = reason
        if status == StatusChange.SUSPENDED:
            await self.sessions.revoke_all_for_user(target, reason=RevokeReason.SUSPENDED)
        else:
            target.failed_login_attempts = 0
            target.locked_until = None

        self.audit.log(
            AuditAction.USER_STATUS_CHANGED,
            actor_id=actor.id,
            resource_type="user",
            resource_id=target.id,
            institution_id=target.institution_id,
            details={"from": previous, "to": status, "reason": reason},
        )
        self._event(
            "user.suspended" if status == StatusChange.SUSPENDED else "user.activated", target, target.institution
        )
        await self.db.commit()
        return await self.users.get_detailed(target.id)

    async def delete_user(self, actor: User, user_id: int, *, expected_role: Role | None = None) -> None:
        """Soft delete: the record is kept for audit history, but the user disappears and cannot log in.
        Email and username become available again; employee codes and admission numbers are never reused."""
        target = await self._load_target(actor, user_id, Action.DELETE, expected_role)
        if target.role == Role.ADMIN and await self.institutions.count_for_admin(target.id) > 0:
            raise ConflictError(
                "This admin still owns institutions. Transfer or delete those institutions first.",
                code="ADMIN_HAS_INSTITUTIONS",
            )

        now = utcnow()
        target.status = UserStatus.DELETED
        target.deleted_at = now
        await self.users.clear_manager_references(target.id)
        await self.resets.consume_all_open(target.id, now=now)
        await self.sessions.revoke_all_for_user(target, reason=RevokeReason.DELETED)

        self.audit.log(
            AuditAction.USER_DELETED,
            actor_id=actor.id,
            resource_type="user",
            resource_id=target.id,
            institution_id=target.institution_id,
        )
        self._event("user.deleted", target, target.institution)
        await self.db.commit()

    async def revoke_access(self, actor: User, user_id: int, *, expected_role: Role | None = None) -> int:
        """Sign the user out everywhere. The account stays active and can log in again."""
        target = await self._load_target(actor, user_id, Action.REVOKE, expected_role)
        revoked = await self.sessions.revoke_all_for_user(target, reason=RevokeReason.ADMIN_REVOKE)
        self.audit.log(
            AuditAction.USER_ACCESS_REVOKED,
            actor_id=actor.id,
            resource_type="user",
            resource_id=target.id,
            institution_id=target.institution_id,
            details={"sessions_revoked": revoked},
        )
        self._event("user.access_revoked", target, target.institution)
        await self.db.commit()
        return revoked

    async def reset_mfa(self, actor: User, user_id: int, *, expected_role: Role | None = None) -> None:
        """Clear a user's two-factor enrolment (lost phone) and sign them out. They enrol again at next login."""
        target = await self._load_target(actor, user_id, Action.REVOKE, expected_role)
        await MfaService(self.db, self.settings, self.audit.ctx).reset_for(actor, target)
        await self.sessions.revoke_all_for_user(target, reason=RevokeReason.ADMIN_REVOKE)
        await self.db.commit()

    # ================================================================== helpers

    async def _load_target(self, actor: User, user_id: int, action: Action, expected_role: Role | None) -> User:
        """Role -> institution -> resource checks for a target user. Targets outside the actor's
        view are reported as not found, so their existence is never disclosed."""
        include_deleted = actor.role == Role.SUPER_ADMIN and action == Action.VIEW
        target = await self.users.get_by_public_id(user_id, include_deleted=include_deleted, detailed=True)
        not_found = NotFoundError("User not found.", code="USER_NOT_FOUND")
        if target is None or (expected_role is not None and target.role != expected_role):
            raise not_found

        if target.id == actor.id:
            if action == Action.VIEW:
                return target
            raise PermissionDeniedError(
                "You cannot perform this action on your own account.", code="SELF_ACTION_NOT_ALLOWED"
            )
        if not (
            policies.can_act_on_role(actor.role, Action.VIEW, target.role)
            and policies.is_user_in_scope(actor, target, target.institution)
        ):
            raise not_found
        if not policies.can_act_on_role(actor.role, action, target.role):
            raise PermissionDeniedError(f"You are not allowed to {_ACTION_VERBS[action]} this user.")
        return target

    async def _ensure_scopes_keep_ownership(self, admin: User, scopes: list[str]) -> None:
        """An admin cannot lose the scope that lets them own organisations they still own."""
        owned = await self.institutions.counts_by_type_for_admin(admin.id)
        for org_type, scope in SCOPE_FOR_ORGANIZATION.items():
            if owned.get(org_type, 0) and scope not in scopes:
                raise ConflictError(
                    f"This admin still owns {org_type}s. Transfer them before removing {scope}.",
                    code="ADMIN_OWNS_ORGANIZATIONS",
                    details=[
                        _detail("scopes", "ADMIN_OWNS_ORGANIZATIONS", f"{scope} is needed while owning {org_type}s")
                    ],
                )

    async def _resolve_institution(
        self, actor: User, role: Role, organization_id: int | None, *, require_active: bool
    ) -> Institution | None:
        if not policies.is_organization_scoped(role):
            if organization_id is not None:
                raise ValidationFailedError(
                    details=[
                        _detail(
                            "organization_id",
                            "NOT_ALLOWED",
                            f"{_ROLE_LABELS[role].capitalize()} accounts do not belong to an institution",
                        )
                    ]
                )
            return None

        institution: Institution | None
        if policies.is_organization_scoped(actor.role):
            institution = await self.institutions.get(actor.institution_id) if actor.institution_id else None
            if institution is None or (organization_id is not None and organization_id != institution.public_id):
                raise PermissionDeniedError("You can only manage users in your own institution.")
        else:
            if organization_id is None:
                raise ValidationFailedError(
                    details=[
                        _detail(
                            "organization_id",
                            "REQUIRED",
                            f"organization_id is required for {_ROLE_LABELS[role]} accounts",
                        )
                    ]
                )
            institution = self._institution_cache.get(organization_id)
            if institution is None:
                institution = await self.institutions.get_by_public_id(organization_id)
                if institution is not None:
                    self._institution_cache[organization_id] = institution
            if institution is None or not policies.can_access_institution(actor, institution):
                raise NotFoundError("Institution not found.", code="INSTITUTION_NOT_FOUND")

        expected_type = organization_type_for(role)
        if expected_type is not None and institution.org_type != expected_type:
            raise ValidationFailedError(
                details=[
                    _detail(
                        "organization_id",
                        "ORGANIZATION_TYPE_MISMATCH",
                        f"{_ROLE_LABELS[role].capitalize()} accounts belong to an {expected_type}",
                    )
                ]
            )
        if require_active and institution.status != InstitutionStatus.ACTIVE:
            raise ConflictError("This institution is not active.", code="INSTITUTION_INACTIVE")
        return institution

    async def _resolve_manager(
        self,
        actor: User,
        role: Role,
        institution: Institution | None,
        manager_user_id: int | None,
        *,
        use_default: bool,
    ) -> User | None:
        if use_default:
            # Staff created by a head report to that head; students created by staff report to that staff member.
            if (
                institution is not None
                and actor.institution_id == institution.id
                and policies.is_valid_manager(actor.role, role)
            ):
                return actor
            return None
        if manager_user_id is None:
            return None
        manager = await self.users.get_by_public_id(manager_user_id)
        if (
            manager is None
            or institution is None
            or manager.institution_id != institution.id
            or manager.status != UserStatus.ACTIVE
            or not policies.is_valid_manager(manager.role, role)
        ):
            raise ValidationFailedError(
                details=[
                    _detail(
                        "manager_user_id",
                        "INVALID_MANAGER",
                        "Must be an active, higher-ranked user in the same institution",
                    )
                ]
            )
        return manager

    def _apply_personal_info(self, user: User, info: PersonalInfoUpdate | Any) -> None:
        profile = self._profile_of(user)
        for name in info.model_fields_set:
            value = getattr(info, name)
            if name in _USER_NAME_FIELDS:
                setattr(user, name, value)
            elif name in _PROFILE_FIELDS:
                setattr(profile, name, value)
        if user.phone and profile.alternate_phone == user.phone:
            raise ValidationFailedError(
                details=[_detail("personal_info.alternate_phone", "DUPLICATE_PHONE", "Must differ from phone")]
            )

    def _profile_of(self, user: User) -> UserProfile:
        if user.profile is None:
            user.profile = UserProfile(
                user_id=user.id,
                preferred_language=self.settings.DEFAULT_LANGUAGE,
                timezone=self.settings.DEFAULT_TIMEZONE,
            )
        return user.profile

    def _raise_if_invalid(self, user: User, *, ignore: frozenset[tuple[str, str]] = frozenset()) -> None:
        """Reject data-rule problems. On updates, problems the record already had (e.g. imported legacy
        data) are ignored, so an update can never make a record worse but is not blocked by old gaps."""
        problems = [p for p in user_record_problems(user, self.settings) if (p["field"], p["code"]) not in ignore]
        if problems:
            raise ValidationFailedError(details=problems)

    def _problem_keys(self, user: User) -> frozenset[tuple[str, str]]:
        return frozenset((p["field"], p["code"]) for p in user_record_problems(user, self.settings))

    async def _ensure_unique(
        self,
        user: User,
        *,
        exclude_id: uuid.UUID | None,
        email: bool,
        username: bool,
        employee_code: bool,
        admission_number: bool,
    ) -> None:
        details = []
        if email and user.email and await self.users.email_taken(user.email, exclude_id=exclude_id):
            details.append(_detail("account.email", "DUPLICATE_EMAIL", "This email address is already in use"))
        if username and await self.users.username_taken(user.username, exclude_id=exclude_id):
            details.append(_detail("account.username", "DUPLICATE_USERNAME", "This username is already taken"))
        code = user.employment.employee_code if user.employment else None
        if (
            employee_code
            and code
            and await self.users.employee_code_taken(code, user.institution_id, exclude_user_id=exclude_id)
        ):
            details.append(
                _detail("employment.employee_code", "DUPLICATE_EMPLOYEE_CODE", "This employee code is already in use")
            )
        number = user.student.admission_number if user.student else None
        if (
            admission_number
            and number
            and user.institution_id
            and await self.users.admission_number_taken(number, user.institution_id, exclude_user_id=exclude_id)
        ):
            details.append(
                _detail(
                    "student.admission_number",
                    "DUPLICATE_ADMISSION_NUMBER",
                    "This admission number is already used in this institution",
                )
            )
        if details:
            raise ConflictError("Some details are already used by another record.", details=details)

    async def _generate_username(
        self, first_name: str, last_name: str, *, avoid: frozenset[str] | set[str] = frozenset()
    ) -> str:
        def slug(value: str) -> str:
            ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
            return re.sub(r"[^a-z0-9]+", "", ascii_value)

        base = ".".join(part for part in (slug(first_name), slug(last_name)) if part)[:24] or "user"
        if not base[0].isalpha():
            base = f"u{base}"[:24]
        candidates = [base] + [f"{base}{secrets.randbelow(9000) + 1000}" for _ in range(8)]
        for candidate in candidates:
            if (
                len(candidate) >= 3
                and candidate not in RESERVED_USERNAMES
                and candidate not in avoid
                and not await self.users.username_taken(candidate)
            ):
                return candidate
        return f"user{secrets.token_hex(6)}"

    def _event(self, event_type: str, user: User, institution: Institution | None) -> None:
        self.audit.event(
            event_type,
            aggregate_type="user",
            aggregate_id=user.id,
            payload=self.users.event_payload(
                user, institution_public_id=institution.public_id if institution else None
            ),
        )


# ====================================================================== module helpers


def _apply_address(profile: UserProfile, address: AddressInput | None) -> None:
    profile.address_line1 = address.line1 if address else None
    profile.address_line2 = address.line2 if address else None
    profile.city = address.city if address else None
    profile.state = address.state if address else None
    profile.postal_code = address.postal_code if address else None
    profile.country = address.country if address else None


def _build_guardians(student_id: uuid.UUID, guardians: list[GuardianInput]) -> list[StudentGuardian]:
    return [
        StudentGuardian(
            id=uuid7(),
            student_id=student_id,
            position=index,
            full_name=guardian.full_name,
            relationship_type=guardian.relationship,
            phone=guardian.phone,
            email=guardian.email,
            occupation=guardian.occupation,
            is_primary=guardian.is_primary,
        )
        for index, guardian in enumerate(guardians)
    ]


def _identity_snapshot(user: User) -> dict[str, Any]:
    return {
        "email": user.email,
        "username": user.username,
        "employee_code": user.employment.employee_code if user.employment else None,
        "admission_number": user.student.admission_number if user.student else None,
    }


def _changed_fields(user: User) -> list[str]:
    """Names of fields changed in memory but not yet written, for the audit log."""
    changed: set[str] = set()
    for prefix, obj in (
        ("", user),
        ("profile", user.profile),
        ("employment", user.employment),
        ("student", user.student),
    ):
        if obj is None:
            continue
        state: InstanceState[Any] = inspect(obj)
        if state.transient or state.pending:
            changed.add(prefix)
            continue
        for attr in state.mapper.column_attrs:
            if state.attrs[attr.key].history.has_changes():
                changed.add(f"{prefix}.{attr.key}" if prefix else attr.key)
    user_state = inspect(user)
    for relationship_name in ("employment", "student", "guardians"):
        if user_state.attrs[relationship_name].history.has_changes():
            changed.add(relationship_name)
    return sorted(name for name in changed if name)
