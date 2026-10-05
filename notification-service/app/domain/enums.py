"""Enums stored as plain strings (not native DB enums) so new values don't need a type migration."""

from enum import StrEnum


class Channel(StrEnum):
    """Delivery channels this service can use. SMS, WhatsApp and push are not built yet
    (see the README's "Not yet wired"); adding one means a new value here and a new class in
    app/channels/."""

    IN_APP = "in_app"
    EMAIL = "email"


class Category(StrEnum):
    """What a notification is about. Users choose per category whether they also want email."""

    ENROLLMENT = "enrollment"
    LEARNING = "learning"
    SUBSCRIPTION = "subscription"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"  # gave up after DELIVERY_MAX_ATTEMPTS; a super admin can retry it


class UserStatus(StrEnum):
    """Local mirror of user-management's user status (see app/models/user_ref.py)."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"
