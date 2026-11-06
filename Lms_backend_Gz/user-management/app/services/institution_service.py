"""Organisations (institutions and employers), addressed by their public ``organization_id``.

One service serves both types; ``org_type`` keeps every query, permission and message to its own type."""

from datetime import timedelta
from typing import Any

from sqlalchemy import ColumnElement, func, inspect, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.context import RequestContext
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.time import start_of_day, utcnow
from app.db.session import commit_or_conflict
from app.db.types import uuid7
from app.domain.enums import SortOrder
from app.models.institution import Institution
from app.models.user import User
from app.permissions import policies
from app.permissions.roles import (
    SCOPE_FOR_ORGANIZATION,
    InstitutionStatus,
    OrganizationType,
    Role,
    StatusChange,
    UserStatus,
)
from app.repositories.institution_repository import InstitutionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.institution import InstitutionSortColumn
from app.schemas.user import AddressInput
from app.services.audit_service import AuditAction, AuditService
from app.services.session_service import RevokeReason, SessionService
from app.utils.query import LIKE_ESCAPE, contains_pattern

_DUPLICATE_CODE = {"field": "code", "code": "DUPLICATE_CODE", "message": "This organisation code is already in use"}
_SORT_COLUMNS = {
    InstitutionSortColumn.CREATED_TIME: Institution.created_at,
    InstitutionSortColumn.NAME: Institution.name,
    InstitutionSortColumn.CODE: Institution.code,
}
_CONTACT_COLUMNS = ("email", "phone", "alternate_phone", "website")
_SIMPLE_COLUMNS = {
    "name": "name",
    "code": "code",
    "type": "institution_type",
    "timezone": "timezone",
    "registration_number": "registration_number",
    "affiliation": "affiliation",
    "industry": "industry",
    "established_year": "established_year",
}

MemberCounts = dict[str, int]


_AUDIT = {
    OrganizationType.INSTITUTION: {
        "created": AuditAction.INSTITUTION_CREATED,
        "updated": AuditAction.INSTITUTION_UPDATED,
        "status_changed": AuditAction.INSTITUTION_STATUS_CHANGED,
        "deleted": AuditAction.INSTITUTION_DELETED,
        "access_revoked": AuditAction.INSTITUTION_ACCESS_REVOKED,
        "exported": AuditAction.INSTITUTIONS_EXPORTED,
    },
    OrganizationType.EMPLOYER: {
        "created": AuditAction.EMPLOYER_CREATED,
        "updated": AuditAction.EMPLOYER_UPDATED,
        "status_changed": AuditAction.EMPLOYER_STATUS_CHANGED,
        "deleted": AuditAction.EMPLOYER_DELETED,
        "access_revoked": AuditAction.EMPLOYER_ACCESS_REVOKED,
        "exported": AuditAction.EMPLOYERS_EXPORTED,
    },
}


class InstitutionService:
    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        ctx: RequestContext,
        org_type: OrganizationType = OrganizationType.INSTITUTION,
    ) -> None:
        self.org_type = org_type
        self.label = org_type.value  # "institution" / "employer" in messages
        self.not_found_code = f"{org_type.value.upper()}_NOT_FOUND"
        self.db = db
        self.settings = settings
        self.institutions = InstitutionRepository(db)
        self.users = UserRepository(db)
        self.sessions = SessionService(db, settings)
        self.audit = AuditService(db, ctx)

    # ================================================================== queries

    async def list_institutions(
        self, actor: User, query: Any
    ) -> tuple[list[Institution], int, bool, dict[Any, MemberCounts]]:
        # `query` is an InstitutionListQuery or an EmployerListQuery (this one service serves both org types,
        # see the module docstring) — the same duck-typed `Any` filter_conditions() below already uses; the two
        # schemas share field names but not a base class, since the field sets genuinely differ (e.g. `industry`
        # vs `type`/`affiliation`).
        conditions = await self.filter_conditions(actor, query)
        if conditions is None:
            return [], 0, True, {}
        column = _SORT_COLUMNS[query.sort_column]
        ordered = column.asc() if query.sort_order == SortOrder.ASC else column.desc()
        items, total, is_exact = await self.institutions.list(
            conditions,
            order_by=[ordered, Institution.id.desc() if query.sort_order == SortOrder.DESC else Institution.id.asc()],
            page=query.page,
            per_page=query.per_page,
        )
        counts = await self.institutions.member_counts([institution.id for institution in items])
        return items, total, is_exact, counts

    async def prepare_export(self, actor: User, query: Any) -> list[ColumnElement[bool]] | None:
        # See the comment on list_institutions(): InstitutionFilters or EmployerFilters, duck-typed on purpose.
        conditions = await self.filter_conditions(actor, query, action="export")
        self.audit.log(
            _AUDIT[self.org_type]["exported"],
            actor_id=actor.id,
            resource_type="institution",
            details={"filters": query.model_dump(mode="json", exclude_none=True)},
        )
        await self.db.commit()
        return conditions

    async def filter_conditions(
        self, actor: User, query: Any, *, action: str = "view"
    ) -> list[ColumnElement[bool]] | None:
        """``action`` is the matrix action the caller needs on the list: ``view``, or ``export`` to download it."""
        if not policies.can_list_organizations(actor, self.org_type, action):
            raise PermissionDeniedError(
                f"You are not allowed to {'download' if action == 'export' else 'see'} institutions."
            )
        conditions: list[ColumnElement[bool]] = [Institution.org_type == self.org_type]
        if query.status == InstitutionStatus.DELETED:
            if actor.role != Role.SUPER_ADMIN:
                raise PermissionDeniedError(f"Only super admins can view deleted {self.label}s.")
            conditions.append(Institution.deleted_at.is_not(None))
        else:
            conditions.append(Institution.deleted_at.is_(None))
            if query.status is not None:
                conditions.append(Institution.status == query.status)

        if actor.role == Role.ADMIN:
            conditions.append(Institution.admin_id == actor.id)
        elif actor.role != Role.SUPER_ADMIN:
            conditions.append(Institution.id == actor.institution_id)

        if query.admin_user_id is not None:
            admin = await self.users.get_by_public_id(query.admin_user_id, include_deleted=True)
            if admin is None:
                return None
            conditions.append(Institution.admin_id == admin.id)
        if getattr(query, "type", None) is not None:
            conditions.append(Institution.institution_type == query.type)
        if query.country:
            conditions.append(Institution.country == query.country)
        for field, column in (
            ("state", Institution.state),
            ("city", Institution.city),
            ("affiliation", Institution.affiliation),
            ("industry", Institution.industry),
        ):
            value = getattr(query, field, None)
            if value:
                conditions.append(func.lower(column) == value.lower())
        if query.created_from:
            conditions.append(Institution.created_at >= start_of_day(query.created_from))
        if query.created_to:
            conditions.append(Institution.created_at < start_of_day(query.created_to + timedelta(days=1)))
        if query.search_text:
            pattern = contains_pattern(query.search_text.lower())
            conditions.append(
                or_(
                    Institution.name.ilike(pattern, escape=LIKE_ESCAPE),
                    Institution.code.ilike(pattern, escape=LIKE_ESCAPE),
                    Institution.city.ilike(pattern, escape=LIKE_ESCAPE),
                )
            )
        return conditions

    async def get_institution(self, actor: User, organization_id: int) -> tuple[Institution, MemberCounts]:
        institution = await self._load_visible(actor, organization_id)
        return institution, await self._counts(institution)

    # ================================================================== commands

    async def create_institution(self, actor: User, data: Any) -> tuple[Institution, MemberCounts]:
        if not policies.can_create_organization(actor, self.org_type):
            raise PermissionDeniedError(f"You are not allowed to create {self.label}s.")

        if actor.role == Role.ADMIN:
            if data.admin_user_id not in (None, actor.public_id):
                raise PermissionDeniedError(f"Admins can only create {self.label}s they own.")
            admin = actor
        elif self.org_type == OrganizationType.EMPLOYER:
            admin = actor  # companies belong to the super admin, who runs hiring (there are no company logins)
        else:
            if data.admin_user_id is None:
                raise ValidationFailedError(
                    details=[
                        {
                            "field": "admin_user_id",
                            "code": "REQUIRED",
                            "message": f"Choose the admin who will own this {self.label}",
                        }
                    ]
                )
            admin = await self._require_active_admin(data.admin_user_id)

        code = getattr(data, "code", None)
        if not code:
            import random, re, string
            clean = re.sub(r"[^A-Z0-9]", "", (data.name or "COMP").upper())[:6] or "COMP"
            for _ in range(10):
                suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
                candidate = f"{clean}-{suffix}"[:20]
                if not await self.institutions.code_taken(candidate):
                    code = candidate
                    break
            else:
                code = f"{clean}-{new_public_id()}"[:20]

        if await self.institutions.code_taken(code):
            raise ConflictError(details=[_DUPLICATE_CODE])

        institution = Institution(
            id=uuid7(),
            public_id=new_public_id(),
            name=data.name,
            code=code,
            org_type=self.org_type,
            institution_type=getattr(data, "type", None),
            industry=getattr(data, "industry", None),
            admin_id=admin.id,
            email=data.contact.email,
            phone=data.contact.phone,
            alternate_phone=data.contact.alternate_phone,
            website=data.contact.website,
            timezone=data.timezone or self.settings.DEFAULT_TIMEZONE,
            registration_number=data.registration_number,
            affiliation=getattr(data, "affiliation", None),
            established_year=data.established_year,
            status=InstitutionStatus.ACTIVE,
            created_by_id=actor.id,
        )
        _apply_address(institution, data.address)
        self.institutions.add(institution)
        self.audit.log(
            _AUDIT[self.org_type]["created"],
            actor_id=actor.id,
            resource_type="institution",
            resource_id=institution.id,
            institution_id=institution.id,
        )
        self._event("created", institution, admin)
        await commit_or_conflict(self.db, "Some details are already used by another record.")
        return await self.institutions.get_detailed(institution.id), {}

    async def update_institution(
        self, actor: User, organization_id: int, data: Any
    ) -> tuple[Institution, MemberCounts]:
        institution = await self._load_manageable(actor, organization_id)
        fields = data.model_fields_set
        admin = institution.admin

        if data.admin_user_id is not None and data.admin_user_id != admin.public_id:
            if not policies.can_reassign_institution_admin(actor):
                raise PermissionDeniedError(f"Only super admins can transfer an {self.label} to another admin.")
            admin = await self._require_active_admin(data.admin_user_id)
            institution.admin_id = admin.id
        if data.code is not None and data.code != institution.code:
            if await self.institutions.code_taken(data.code, exclude_id=institution.id):
                raise ConflictError(details=[_DUPLICATE_CODE])

        for field, column in _SIMPLE_COLUMNS.items():
            if field in fields:
                setattr(institution, column, getattr(data, field))
        if data.contact is not None:
            for name in data.contact.model_fields_set & set(_CONTACT_COLUMNS):
                setattr(institution, name, getattr(data.contact, name))
            if institution.alternate_phone and institution.alternate_phone == institution.phone:
                raise ValidationFailedError(
                    details=[
                        {
                            "field": "contact.alternate_phone",
                            "code": "DUPLICATE_PHONE",
                            "message": "Must differ from phone",
                        }
                    ]
                )
        if data.address is not None:
            _apply_address(institution, data.address)

        state = inspect(institution)
        changed_fields = sorted(a.key for a in state.mapper.column_attrs if state.attrs[a.key].history.has_changes())
        if not changed_fields:
            return institution, await self._counts(institution)

        self.audit.log(
            _AUDIT[self.org_type]["updated"],
            actor_id=actor.id,
            resource_type="institution",
            resource_id=institution.id,
            institution_id=institution.id,
            details={"changed_fields": changed_fields},
        )
        self._event("updated", institution, admin)
        await commit_or_conflict(self.db, "Some details are already used by another record.")
        refreshed = await self.institutions.get_detailed(institution.id)
        return refreshed, await self._counts(refreshed)

    async def change_status(
        self, actor: User, organization_id: int, status: StatusChange, reason: str | None
    ) -> tuple[Institution, MemberCounts]:
        institution = await self._load_manageable(actor, organization_id, "revoke")
        if institution.status != status:
            previous = institution.status
            institution.status = status
            institution.status_reason = reason
            if status == StatusChange.SUSPENDED:
                await self.sessions.revoke_all_for_institution(
                    institution.id, reason=RevokeReason.INSTITUTION_SUSPENDED
                )
            self.audit.log(
                _AUDIT[self.org_type]["status_changed"],
                actor_id=actor.id,
                resource_type="institution",
                resource_id=institution.id,
                institution_id=institution.id,
                details={"from": previous, "to": status, "reason": reason},
            )
            self._event(
                "suspended" if status == StatusChange.SUSPENDED else "activated",
                institution,
                institution.admin,
            )
            await self.db.commit()
            institution = await self.institutions.get_detailed(institution.id)
        return institution, await self._counts(institution)

    async def delete_institution(self, actor: User, organization_id: int) -> None:
        """Soft delete. Members keep their records but lose all access."""
        institution = await self._load_manageable(actor, organization_id, "delete")
        institution.status = InstitutionStatus.DELETED
        institution.deleted_at = utcnow()
        revoked = await self.sessions.revoke_all_for_institution(
            institution.id, reason=RevokeReason.INSTITUTION_DELETED
        )
        self.audit.log(
            _AUDIT[self.org_type]["deleted"],
            actor_id=actor.id,
            resource_type="institution",
            resource_id=institution.id,
            institution_id=institution.id,
            details={"sessions_revoked": revoked},
        )
        self._event("deleted", institution, institution.admin)
        await self.db.commit()

    async def revoke_access(self, actor: User, organization_id: int) -> int:
        """Sign out every member of the institution. Accounts stay active."""
        institution = await self._load_manageable(actor, organization_id, "revoke")
        revoked = await self.sessions.revoke_all_for_institution(institution.id, reason=RevokeReason.INSTITUTION_REVOKE)
        self.audit.log(
            _AUDIT[self.org_type]["access_revoked"],
            actor_id=actor.id,
            resource_type="institution",
            resource_id=institution.id,
            institution_id=institution.id,
            details={"sessions_revoked": revoked},
        )
        self._event("access_revoked", institution, institution.admin)
        await self.db.commit()
        return revoked

    # ================================================================== helpers

    async def _load_visible(self, actor: User, organization_id: int) -> Institution:
        institution = await self.institutions.get_by_public_id(
            organization_id, include_deleted=actor.role == Role.SUPER_ADMIN, detailed=True
        )
        if (
            institution is None
            or institution.org_type != self.org_type
            or not policies.can_access_institution(actor, institution)
        ):
            raise NotFoundError(f"{self.label.capitalize()} not found.", code=self.not_found_code)
        return institution

    async def _load_manageable(self, actor: User, organization_id: int, action: str = "update") -> Institution:
        """``action``: the matrix action needed: ``update``, ``revoke`` (suspend, reactivate, sign out) or ``delete``."""
        institution = await self._load_visible(actor, organization_id)
        if institution.deleted_at is not None:
            raise NotFoundError(f"{self.label.capitalize()} not found.", code=self.not_found_code)
        if not policies.can_manage_institution(actor, institution, action):
            raise PermissionDeniedError(f"You are not allowed to manage this {self.label}.")
        return institution

    async def _counts(self, institution: Institution) -> MemberCounts:
        return (await self.institutions.member_counts([institution.id])).get(institution.id, {})

    async def _require_active_admin(self, admin_user_id: int) -> User:
        admin = await self.users.get_by_public_id(admin_user_id)
        scope = SCOPE_FOR_ORGANIZATION[self.org_type]
        if admin is None or admin.role != Role.ADMIN or admin.status != UserStatus.ACTIVE:
            raise ValidationFailedError(
                details=[
                    {
                        "field": "admin_user_id",
                        "code": "INVALID_ADMIN",
                        "message": "Must be the user_id of an active admin",
                    }
                ]
            )
        if scope not in admin.scope_list:
            raise ValidationFailedError(
                details=[
                    {
                        "field": "admin_user_id",
                        "code": "ADMIN_SCOPE_REQUIRED",
                        "message": f"The admin needs the {scope} scope to own {self.label}s",
                    }
                ]
            )
        return admin

    def _event(self, change: str, institution: Institution, admin: User) -> None:
        self.audit.event(
            f"{self.org_type.value}.{change}",
            aggregate_type="institution",
            aggregate_id=institution.id,
            payload=self.institutions.event_payload(institution, admin_public_id=admin.public_id),
        )


def _apply_address(institution: Institution, address: AddressInput) -> None:
    institution.address_line1 = address.line1
    institution.address_line2 = address.line2
    institution.city = address.city
    institution.state = address.state
    institution.postal_code = address.postal_code
    institution.country = address.country
