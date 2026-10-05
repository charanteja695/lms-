"""What the signed-in person may do, expressed for clients.

Clients never re-implement rules: they render buttons, menus and form sections from these values, and the
server still checks every request. Everything here is derived from ``policies`` and ``validators.user_rules``,
so a rule changes in exactly one place.
"""

from app.core.config import Settings
from app.models.institution import Institution
from app.models.user import User
from app.permissions import policies
from app.permissions.policies import Action
from app.permissions.roles import (
    DEFAULT_ADMIN_SCOPES,
    EMPLOYER_MEMBER_ROLES,
    INSTITUTION_MEMBER_ROLES,
    AdminScope,
    OrganizationType,
    Role,
    UserStatus,
    organization_type_for,
)

# ------------------------------------------------------------------ per record


class UserAction:
    UPDATE = "update"
    SUSPEND = "suspend"
    ACTIVATE = "activate"
    REVOKE_SESSIONS = "revoke_sessions"
    RESET_MFA = "reset_mfa"
    SET_PASSWORD = "set_password"
    DELETE = "delete"


class OrganizationAction:
    UPDATE = "update"
    SUSPEND = "suspend"
    ACTIVATE = "activate"
    REVOKE_SESSIONS = "revoke_sessions"
    DELETE = "delete"
    ADD_MEMBER = "add_member"
    VIEW_MEMBERS = "view_members"


def user_actions(actor: User, target: User) -> list[str]:
    """Actions ``actor`` may take on a user they can already see (lists and details are pre-scoped)."""
    if target.id == actor.id or target.status == UserStatus.DELETED:
        return []

    def allowed(action: Action) -> bool:
        return policies.can_act_on_role(actor.role, action, target.role)

    actions: list[str] = []
    if allowed(Action.UPDATE):
        actions.append(UserAction.UPDATE)
    if allowed(Action.CHANGE_STATUS):
        actions.append(UserAction.SUSPEND if target.status == UserStatus.ACTIVE else UserAction.ACTIVATE)
    if allowed(Action.REVOKE):
        actions += [UserAction.REVOKE_SESSIONS, UserAction.RESET_MFA]
    if allowed(Action.UPDATE):
        actions.append(UserAction.SET_PASSWORD)
    if allowed(Action.DELETE):
        actions.append(UserAction.DELETE)
    return actions


def institution_actions(actor: User, organization: Institution) -> list[str]:
    """Actions on an institution or employer the actor can already see."""
    actions: list[str] = []
    if organization.status != UserStatus.DELETED and policies.can_manage_institution(actor, organization):
        actions.append(OrganizationAction.UPDATE)
        active = organization.status == UserStatus.ACTIVE
        actions.append(OrganizationAction.SUSPEND if active else OrganizationAction.ACTIVATE)
        actions += [OrganizationAction.REVOKE_SESSIONS, OrganizationAction.DELETE]
    if organization.deleted_at is None and policies.can_access_institution(actor, organization):
        is_employer = organization.org_type == OrganizationType.EMPLOYER
        member_roles = EMPLOYER_MEMBER_ROLES if is_employer else INSTITUTION_MEMBER_ROLES
        if member_roles & policies.allowed_target_roles(actor.role, Action.CREATE):
            actions.append(OrganizationAction.ADD_MEMBER)
        if member_roles & policies.allowed_target_roles(actor.role, Action.VIEW):
            actions.append(OrganizationAction.VIEW_MEMBERS)
    return actions


# ------------------------------------------------------------------ for the signed-in person


MANAGED_ORDER = (Role.ADMIN, Role.INSTITUTION_HEAD, Role.STAFF, Role.STUDENT, Role.EMPLOYER_ADMIN, Role.RECRUITER)


def _roles(actor: User, action: Action, *, exclude: frozenset[Role] = frozenset()) -> list[str]:
    allowed = policies.allowed_target_roles(actor.role, action)
    return [role.value for role in MANAGED_ORDER if role in allowed and role not in exclude]


def _organization_rights(actor: User, org_type: OrganizationType, statuses: list[str]) -> dict[str, object]:
    return {
        "create": policies.can_create_organization(actor, org_type),
        "filter_statuses": statuses,
        "filter_by_admin": actor.role == Role.SUPER_ADMIN,
        "reassign_admin": policies.can_reassign_institution_admin(actor),
    }


_STAFF = Role.STAFF
_HEAD = Role.INSTITUTION_HEAD
_STUDENT = Role.STUDENT
_EMPLOYER_ADMIN = Role.EMPLOYER_ADMIN
_RECRUITER = Role.RECRUITER

# One row per other backend service's menu entry (docs/PRODUCT.md §6): the member roles and the admin scopes
# that each reach it, read straight from that service's own "who may do what" table (docs/API.md) so a role
# either has the module (1) or does not (0) in exactly one place — no separate per-role tuple to keep in sync.
# Coarse show/hide only: each service's own API still decides what within its section this person may do.
_MODULE_ACCESS: dict[str, tuple[frozenset[Role], frozenset[AdminScope]]] = {
    "catalog": (frozenset({_STUDENT, _STAFF, _HEAD}), frozenset({AdminScope.CONTENT_AUTHOR, AdminScope.CONTENT_REVIEW})),
    "subscriptions": (frozenset({_HEAD}), frozenset({AdminScope.ACCOUNTS_MANAGE})),
    "learning": (frozenset({_STUDENT, _STAFF, _HEAD}), frozenset({AdminScope.ACCOUNTS_MANAGE})),
    "code_execution": (frozenset({_STUDENT, _STAFF, _HEAD}), frozenset({AdminScope.CONTENT_AUTHOR, AdminScope.CONTENT_REVIEW})),
    "assessments": (
        frozenset({_STUDENT, _STAFF, _HEAD, _EMPLOYER_ADMIN, _RECRUITER}),
        frozenset({AdminScope.CONTENT_AUTHOR, AdminScope.CONTENT_REVIEW, AdminScope.EXAMS_MANAGE}),
    ),
    "proctoring": (frozenset({_STUDENT, _STAFF, _HEAD, _EMPLOYER_ADMIN, _RECRUITER}), frozenset({AdminScope.EXAMS_MANAGE})),
    "certificates": (
        frozenset({_STUDENT, _STAFF, _HEAD}),
        frozenset({AdminScope.CONTENT_AUTHOR, AdminScope.CONTENT_REVIEW, AdminScope.EXAMS_MANAGE}),
    ),
    "ai_tutor": (
        frozenset({_STUDENT, _STAFF, _HEAD}),
        frozenset({AdminScope.CONTENT_AUTHOR, AdminScope.SUPPORT_MANAGE, AdminScope.AI_MANAGE}),
    ),
    "support": (frozenset({_STUDENT, _STAFF, _HEAD}), frozenset({AdminScope.EXAMS_MANAGE, AdminScope.SUPPORT_MANAGE})),
    "career": (frozenset({_STUDENT, _STAFF, _HEAD}), frozenset({AdminScope.CAREERS_MANAGE})),
    "job_portal": (frozenset({_STUDENT, _STAFF, _HEAD, _EMPLOYER_ADMIN, _RECRUITER}), frozenset({AdminScope.CAREERS_MANAGE})),
    "ai_interview": (frozenset({_STUDENT, _EMPLOYER_ADMIN, _RECRUITER}), frozenset({AdminScope.CAREERS_MANAGE})),
    "notifications": (frozenset({_STUDENT, _STAFF, _HEAD, _EMPLOYER_ADMIN, _RECRUITER}), frozenset()),
    "analytics": (
        frozenset({_STAFF, _HEAD, _EMPLOYER_ADMIN, _RECRUITER}),
        frozenset({
            AdminScope.CONTENT_REVIEW, AdminScope.EXAMS_MANAGE, AdminScope.SUPPORT_MANAGE,
            AdminScope.CAREERS_MANAGE, AdminScope.AI_MANAGE, AdminScope.BILLING_MANAGE, AdminScope.ANALYTICS_VIEW,
        }),
    ),
    "billing": (frozenset({_HEAD, _EMPLOYER_ADMIN}), frozenset({AdminScope.BILLING_MANAGE})),
}


def _module_sections(actor: User, role: Role) -> list[str]:
    """The other backend services' menu entries this person's role and scopes reach, from the single
    ``_MODULE_ACCESS`` table above."""
    if role == Role.SUPER_ADMIN:
        return list(_MODULE_ACCESS)
    scopes = {AdminScope(scope) for scope in actor.scope_list} if role == Role.ADMIN else frozenset[AdminScope]()
    return [module for module, (roles, admin_scopes) in _MODULE_ACCESS.items() if role in roles or scopes & admin_scopes]


def my_permissions(actor: User) -> dict[str, object]:
    """Menu sections, list filters and create rights for the signed-in person."""
    role = Role(actor.role)
    is_super = role == Role.SUPER_ADMIN
    member_view_roles = _roles(actor, Action.VIEW, exclude=frozenset({Role.ADMIN}))
    member_create_roles = _roles(actor, Action.CREATE, exclude=frozenset({Role.ADMIN}))
    statuses = [UserStatus.ACTIVE.value, UserStatus.SUSPENDED.value] + ([UserStatus.DELETED.value] if is_super else [])
    organization_type = organization_type_for(role)

    sections = ["dashboard"]
    if is_super:
        sections.append("admins")
    if policies.can_create_organization(actor, OrganizationType.INSTITUTION):
        sections.append("institutions")
    if policies.can_create_organization(actor, OrganizationType.EMPLOYER):
        sections.append("employers")
    if organization_type is not None:
        sections.append("my_organization")
    if member_view_roles:
        sections += ["users", "downloads"]
    if role in (Role.SUPER_ADMIN, Role.ADMIN, Role.INSTITUTION_HEAD, Role.EMPLOYER_ADMIN):
        sections.append("audit_logs")
    sections += _module_sections(actor, role)
    sections += ["profile", "security"]

    return {
        "role": role.value,
        "organization_type": organization_type.value if organization_type else None,
        "scopes": policies.token_scopes(actor),
        "sections": sections,
        "users": {
            "view_roles": member_view_roles,
            "create_roles": member_create_roles,
            "can_import": bool(member_create_roles),
            "can_export": bool(member_view_roles),
            "filter_statuses": statuses,
            "filter_by_institution": role in (Role.SUPER_ADMIN, Role.ADMIN),
        },
        "admins": {"view": is_super, "create": is_super},
        "institutions": _organization_rights(actor, OrganizationType.INSTITUTION, statuses),
        "employers": _organization_rights(actor, OrganizationType.EMPLOYER, statuses),
        "admin_scopes": [scope.value for scope in AdminScope] if is_super else [],
        "audit_logs": {"view": "audit_logs" in sections},
    }


# ------------------------------------------------------------------ user form

_MANAGER_ROLE = {Role.STAFF: Role.INSTITUTION_HEAD, Role.STUDENT: Role.STAFF, Role.RECRUITER: Role.EMPLOYER_ADMIN}
_EMPLOYEE_ROLES = frozenset({Role.ADMIN, Role.INSTITUTION_HEAD, Role.STAFF, Role.EMPLOYER_ADMIN, Role.RECRUITER})


def user_form_options(actor: User, settings: Settings, *, role: str | None, target: User | None) -> dict[str, object]:
    """Which roles, sections and fields the create/edit user form shows for ``role``.

    ``target`` is the user being edited (None when creating). Required fields mirror
    ``validators.user_rules`` so the form marks exactly what the server will require.
    """
    actor_role = Role(actor.role)
    actor_scoped = policies.is_organization_scoped(actor_role)
    if target is None:
        selectable = _roles(actor, Action.CREATE)
    else:
        current = Role(target.role)
        switchable = {Role.INSTITUTION_HEAD, Role.STAFF}
        selectable = (
            [r for r in _roles(actor, Action.UPDATE) if Role(r) in switchable]
            if current in switchable
            else [current.value]
        )

    chosen = Role(role) if role in {r.value for r in Role} else (Role(target.role) if target else None)
    scoped = chosen is not None and policies.is_organization_scoped(chosen)
    organization_type = organization_type_for(chosen) if chosen else None
    is_student = chosen == Role.STUDENT
    is_employee = chosen in _EMPLOYEE_ROLES

    required = ["role", "personal_info.first_name", "personal_info.last_name"]
    if not is_student:
        required.append("account.email")
    if is_employee:
        required.append("personal_info.phone")
    if chosen in (Role.INSTITUTION_HEAD, Role.STAFF):
        required.append("employment.employee_code")
    if is_student:
        required += ["personal_info.date_of_birth", "student.admission_number"]
    if scoped:
        required.append("organization_id")

    manager_role = _MANAGER_ROLE.get(chosen) if chosen else None
    return {
        "roles": selectable,
        "role_editable": len(selectable) > 1,
        "organization": {
            "shown": scoped,
            "type": organization_type.value if organization_type else None,
            "required": scoped,
            "selectable": scoped and not actor_scoped,
            "fixed": actor.institution_id is not None and actor_scoped,
        },
        "scopes": {
            "shown": chosen == Role.ADMIN,
            "options": [scope.value for scope in AdminScope],
            "default": [scope.value for scope in DEFAULT_ADMIN_SCOPES] if target is None else [],
        },
        "manager": {
            "shown": manager_role is not None,
            "role": manager_role.value if manager_role else None,
            "defaults_to_you": actor_scoped and manager_role is not None and actor_role == manager_role,
        },
        "sections": {
            "address": True,
            "employment": is_employee,
            "student": is_student,
            "guardians": is_student,
        },
        "guardians": {"max": 4, "required_below_age": settings.GUARDIAN_REQUIRED_BELOW_AGE},
        "initial_password": {
            "allowed": target is None,
            "min_length": settings.PASSWORD_MIN_LENGTH,
            "generated_without_email": target is None and is_student,
        },
        "email_optional": is_student,
        "required_fields": required,
        "defaults": {
            "language": settings.DEFAULT_LANGUAGE,
            "timezone": settings.DEFAULT_TIMEZONE,
            "country": settings.DEFAULT_COUNTRY_CODE,
        },
    }
