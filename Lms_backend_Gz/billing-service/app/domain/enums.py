"""Enums stored as plain strings (not native DB enums) so new values don't need a type migration."""

from enum import StrEnum


class PriceKind(StrEnum):
    COURSE_SEAT = "course_seat"  # code = a course id; the amount is per seat per 365 days
    EMPLOYER_PLAN = "employer_plan"  # code = a tier name; the amount is for the whole plan


class QuoteStatus(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class InvoiceKind(StrEnum):
    SUBSCRIPTION = "subscription"
    PLAN = "plan"
    COURSE = "course"  # an individual learner's course purchase


class PurchaseStatus(StrEnum):
    PENDING = "pending"  # invoiced, waiting for payment
    PAID = "paid"  # access granted (course.purchased announced)
    CANCELLED = "cancelled"  # its invoice was voided


class InvoiceStatus(StrEnum):
    DRAFT = "draft"  # system-generated, still editable
    ISSUED = "issued"  # immutable: a correction is a credit note
    PAID = "paid"
    OVERDUE = "overdue"
    VOID = "void"


class PaymentMethod(StrEnum):
    MANUAL = "manual"  # bank transfer, cheque, UPI reference noted by an admin
    GATEWAY = "gateway"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PlanStatus(StrEnum):
    PENDING = "pending"  # bought, invoice not yet paid
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
