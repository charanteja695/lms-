"""Who may do what (docs/PRODUCT.md §5.10), as permissions from the access token (user-management's catalog).

  billing.contact     their own organisation's billing profile, quotes, invoices and payments
                      (by default an institution head or an employer admin; a super admin may grant or remove it per person)
  billing.plans.buy   buy hiring plans for their own company (by default an employer admin)
  billing.manage      every organisation's: prices, quotes (discounts), invoices (edit drafts, issue, void), manual payments, credit notes
  super admin         everything
Whose data: a contact acts for their own organisation only; billing.manage for any.
"""

from enum import StrEnum

from app.core.security import AccessTokenClaims


class Permission(StrEnum):
    BILLING_MANAGE = "billing.manage"
    BILLING_CONTACT = "billing.contact"
    PLANS_BUY = "billing.plans.buy"
    STORE_BUY = "store.buy"  # a self-registered learner buying courses for themselves (never a super admin's power)


def can_manage_billing(auth: AccessTokenClaims) -> bool:
    return auth.can(Permission.BILLING_MANAGE) or auth.role == "super_admin"


def is_billing_contact(auth: AccessTokenClaims, action: str = "view") -> bool:
    """Deals with billing for their own organisation (the Billing page's cells): ``view`` invoices and quotes,
    ``update`` the billing profile, ask for and accept quotes, and pay."""
    return auth.organization_id is not None and auth.can_act(f"billing.{action}", Permission.BILLING_CONTACT)


def can_buy_plans(auth: AccessTokenClaims) -> bool:
    return auth.organization_id is not None and auth.can(Permission.PLANS_BUY)


def can_buy_courses(auth: AccessTokenClaims) -> bool:
    if auth.role in ("super_admin", "admin", "staff", "institution_head"):
        return False
    return auth.has_scope(Permission.STORE_BUY) or (auth.role == "student" and not auth.organization_id)


def is_independent_student(auth: AccessTokenClaims) -> bool:
    return auth.role == "student" and not auth.organization_id

def is_student_user(auth: AccessTokenClaims) -> bool:
    return auth.role == "student" or can_buy_courses(auth)


def is_institution_head(auth: AccessTokenClaims) -> bool:
    return auth.organization_id is not None and auth.role == "institution_head"


def owns(auth: AccessTokenClaims, org_id: int, action: str = "view") -> bool:
    return can_manage_billing(auth) or (is_billing_contact(auth, action) and auth.organization_id == org_id)
