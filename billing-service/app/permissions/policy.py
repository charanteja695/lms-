"""Who may do what (docs/PRODUCT.md §5.10).

  institution head / employer admin   their own organisation's billing profile, quotes, invoices and payments; an employer admin also buys plans
  billing.manage                      every organisation's: prices, quotes (discounts), invoices (edit drafts, issue, void), manual payments, credit notes
  super admin                         everything
Staff, recruiters and students see no billing.
"""

from enum import StrEnum

from app.core.security import AccessTokenClaims
from app.permissions.roles import Role


class Scope(StrEnum):
    BILLING_MANAGE = "billing.manage"  # mirrors user-management's AdminScope


def can_manage_billing(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.SUPER_ADMIN or auth.has_scope(Scope.BILLING_MANAGE.value)


def is_billing_contact(auth: AccessTokenClaims) -> bool:
    """The person who deals with billing for an organisation: an institution's head or an employer's admin."""
    return auth.role in {Role.INSTITUTION_HEAD, Role.EMPLOYER_ADMIN} and auth.organization_id is not None


def owns(auth: AccessTokenClaims, org_id: int) -> bool:
    return can_manage_billing(auth) or (is_billing_contact(auth) and auth.organization_id == org_id)
