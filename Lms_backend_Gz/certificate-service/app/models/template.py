from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.domain.enums import TemplateStatus


class CertificateTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """What a course's certificate looks like (docs/PRODUCT.md §5.4 "a template per course"). ``course_id`` empty is the
    platform default, used for any course without a template of its own. A certificate snapshots the template it was
    issued with, so editing or replacing a template never changes a certificate already issued."""

    __tablename__ = "certificate_templates"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    course_id: Mapped[int | None] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(10), default=TemplateStatus.DRAFT, server_default=TemplateStatus.DRAFT)
    title_text: Mapped[str] = mapped_column(String(120))
    body_text: Mapped[str] = mapped_column(Text)  # with {placeholders}, see app/render/layout.py
    footer_text: Mapped[str | None] = mapped_column(String(300))
    accent_color: Mapped[str] = mapped_column(String(7))  # #RRGGBB
    signatories: Mapped[list[dict[str, Any]]] = mapped_column(JSONType)  # [{"name", "title"}]
    grade_bands: Mapped[list[dict[str, Any]]] = mapped_column(JSONType)  # [{"min_percent", "label"}], best first
    created_by: Mapped[int] = mapped_column(BigInteger)
    activated_at: Mapped[datetime | None]

    __table_args__ = (Index("ix_certificate_templates_course_status", "course_id", "status"),)
