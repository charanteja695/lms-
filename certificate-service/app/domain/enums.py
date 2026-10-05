"""Enums stored as plain strings (not native DB enums) so new values don't need a type migration."""

from enum import StrEnum


class TemplateStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"  # used for new certificates; at most one per course (and one platform default)
    ARCHIVED = "archived"


class CertificateStatus(StrEnum):
    ISSUED = "issued"
    REVOKED = "revoked"


class PdfStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"  # gave up; an admin can regenerate
