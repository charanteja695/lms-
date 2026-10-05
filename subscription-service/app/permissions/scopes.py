"""Platform admin scope this service checks. Value mirrors user-management's ``AdminScope``
(see ``lms-backend/user-management/app/permissions/roles.py``) since it travels in the same
access token; this service never grants or revokes it, only reads it from the token."""

from enum import StrEnum


class Scope(StrEnum):
    ACCOUNTS_MANAGE = "accounts.manage"  # approve/reject course requests, manage plans and subscriptions
