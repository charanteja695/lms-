"""Admin scopes this service checks (values mirror user-management's ``AdminScope``; see docs/PRODUCT.md line 76:
"ai.manage: AI policies, prompts, model routing, quotas")."""

from enum import StrEnum


class Scope(StrEnum):
    AI_MANAGE = "ai.manage"
