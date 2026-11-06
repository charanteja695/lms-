"""Admin scopes this service checks (values mirror user-management's ``AdminScope``)."""

from enum import StrEnum


class Scope(StrEnum):
    SUPPORT_MANAGE = "support.manage"  # platform support: every queue, assignment, SLA policies, canned replies, reports
    EXAMS_MANAGE = "exams.manage"  # the exam team: the integrity queue
