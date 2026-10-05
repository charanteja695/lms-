from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType


class ResumeTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A layout. Every template is single-column, text-only and uses standard section headings, so that an applicant tracking
    system reads it in order; they differ in typography and spacing (see app/rendering/templates.py)."""

    __tablename__ = "resume_templates"

    key: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(300))
    config: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    ats_safe: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Resume(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A resume for one target role. ``draft`` is what the student is editing; a version is a frozen, rendered snapshot."""

    __tablename__ = "resumes"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(120))
    target_role: Mapped[str | None] = mapped_column(String(120))
    template_key: Mapped[str] = mapped_column(String(30))
    job_description: Mapped[str | None] = mapped_column(Text)  # what this resume is tailored to
    draft: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    draft_revision: Mapped[int] = mapped_column(Integer, default=0)  # optimistic concurrency for edits
    latest_version_no: Mapped[int] = mapped_column(Integer, default=0)
    # sharing: a public link pinned to one version
    share_token: Mapped[str | None] = mapped_column(String(64), unique=True)
    share_version_no: Mapped[int | None] = mapped_column(Integer)
    share_show_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    share_expires_at: Mapped[datetime | None]
    share_views: Mapped[int] = mapped_column(Integer, default=0)
    deleted_at: Mapped[datetime | None]

    __table_args__ = (Index("ix_resumes_user", "user_id", "deleted_at"),)


class ResumeVersion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "resume_versions"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    resume_id: Mapped[Any] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))
    version_no: Mapped[int] = mapped_column(Integer)
    label: Mapped[str | None] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(10))
    template_key: Mapped[str] = mapped_column(String(30))
    draft: Mapped[dict[str, Any]] = mapped_column(JSONType)  # the draft as it was: restoring copies it back
    document: Mapped[dict[str, Any]] = mapped_column(JSONType)  # the resolved document: what a PDF / share / JSON Resume shows
    ats_score: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("resume_id", "version_no", name="uq_resume_versions_no"),)
