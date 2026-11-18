"""Course Institutional Pricing Model: Admin configuration for bulk course purchasing."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.core.time import utcnow


class CourseInstitutionalPricing(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Institutional pricing configuration per course, supporting Fixed, Monthly, and Hourly pricing models."""

    __tablename__ = "course_institutional_pricings"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    course_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    course_title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100), default="Technology")

    # Individual selling price for independent students (Model A)
    individual_price_paise: Mapped[int] = mapped_column(BigInteger, default=199900)

    # Institutional Pricing Method: "fixed" | "monthly" | "hourly"
    pricing_method: Mapped[str] = mapped_column(String(30), default="fixed")

    # Option 1: Fixed price per student per course
    fixed_price_paise: Mapped[int] = mapped_column(BigInteger, default=30000)

    # Option 2: Price per student per month
    monthly_price_paise: Mapped[int] = mapped_column(BigInteger, default=10000)
    monthly_billing_rule: Mapped[str] = mapped_column(String(20), default="pro_rata")  # "pro_rata" | "round_up"

    # Option 3: Price per student per learning hour
    hourly_price_paise: Mapped[int] = mapped_column(BigInteger, default=1000)
    billable_hours: Mapped[int] = mapped_column(Integer, default=40)

    # Tiered Bulk Discounts (JSON list of ranges)
    # [{"min_students": 1, "max_students": 49, "discount_percent": 0, "fixed_discount_paise": 0}, ...]
    bulk_discount_tiers: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)

    # Tax & Limits
    gst_percent: Mapped[int] = mapped_column(Integer, default=18)
    min_students: Mapped[int] = mapped_column(Integer, default=1)
    max_students: Mapped[int] = mapped_column(Integer, default=50000)
    min_duration_days: Mapped[int] = mapped_column(Integer, default=7)
    max_duration_days: Mapped[int] = mapped_column(Integer, default=1825)

    effective_from: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    __table_args__ = (
        Index("ix_course_inst_pricing_cid_active", "course_id", "is_active"),
    )


class CoursePricingChangeAudit(UUIDPrimaryKeyMixin, Base):
    """Immutable audit log for every change made to course prices, discounts, GST, and rules."""

    __tablename__ = "course_pricing_change_audits"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    course_id: Mapped[int] = mapped_column(BigInteger, index=True)
    course_title: Mapped[str] = mapped_column(String(255), default="")

    previous_individual_price_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    new_individual_price_paise: Mapped[int] = mapped_column(BigInteger, default=0)

    previous_institutional_price_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    new_institutional_price_paise: Mapped[int] = mapped_column(BigInteger, default=0)

    pricing_method: Mapped[str] = mapped_column(String(30), default="fixed")
    gst_percent: Mapped[int] = mapped_column(Integer, default=18)

    admin_user_id: Mapped[int] = mapped_column(BigInteger, default=0)
    admin_email: Mapped[str] = mapped_column(String(255), default="")
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    effective_from: Mapped[datetime | None] = mapped_column(nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        Index("ix_course_pricing_audit_cid", "course_id", "created_at"),
    )
