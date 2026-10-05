from app.core.exceptions import PermissionDeniedError
from app.models.institution import Institution
from app.models.user import User
from app.permissions import policies
from app.permissions.roles import InstitutionStatus, UserStatus
from app.repositories.institution_repository import InstitutionRepository


def ensure_user_active(user: User) -> None:
    if user.deleted_at is not None or user.status != UserStatus.ACTIVE:
        raise PermissionDeniedError("Your account is not active. Contact your administrator.", code="ACCOUNT_INACTIVE")


async def ensure_institution_access(user: User, institutions: InstitutionRepository) -> Institution | None:
    """Organisation members (institutions and employers) may only act while their organisation is active."""
    if not policies.is_organization_scoped(user.role):
        return None
    institution = await institutions.get(user.institution_id) if user.institution_id else None
    return check_institution_active(user, institution)


def check_institution_active(user: User, institution: Institution | None) -> Institution | None:
    """Same rule as ensure_institution_access, for an institution that is already loaded."""
    if not policies.is_organization_scoped(user.role):
        return None
    if institution is None or institution.deleted_at is not None or institution.status != InstitutionStatus.ACTIVE:
        raise PermissionDeniedError(
            "Your organisation's access is currently disabled. Contact your administrator.",
            code="INSTITUTION_INACTIVE",
        )
    return institution
