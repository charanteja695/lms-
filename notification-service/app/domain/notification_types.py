"""Every notification this service can send: its category, the placeholders a template may use and
the default wording. Templates use ``string.Template`` syntax (``${course_title}``): no attribute
access or code, so an admin-edited template can never execute anything. A super admin can override
the wording per channel (app/models/template_override.py); the placeholders stay fixed."""

from dataclasses import dataclass

from app.domain.enums import Category

COMMON_VARIABLES: tuple[str, ...] = ("first_name", "app_url")

_FOOTER = "\n\nOpen the LMS: ${app_url}"


@dataclass(frozen=True, slots=True)
class NotificationType:
    key: str
    category: Category
    variables: tuple[str, ...]  # placeholders beyond COMMON_VARIABLES
    subject: str
    body: str
    email: bool = True  # also sent by email (in-app always), subject to the user's preference

    @property
    def allowed_variables(self) -> frozenset[str]:
        return frozenset((*COMMON_VARIABLES, *self.variables))


_TYPES: tuple[NotificationType, ...] = (
    NotificationType(
        key="enrollment.created",
        category=Category.ENROLLMENT,
        variables=("course_title",),
        subject="You are enrolled in ${course_title}",
        body="Hello ${first_name},\n\nYou have been enrolled in ${course_title}. You can start learning now." + _FOOTER,
    ),
    NotificationType(
        key="enrollment.removed",
        category=Category.ENROLLMENT,
        variables=("course_title",),
        subject="Your enrolment in ${course_title} has ended",
        body="Hello ${first_name},\n\nYou are no longer enrolled in ${course_title}. Contact your institution if this is unexpected."
        + _FOOTER,
    ),
    NotificationType(
        key="course.eligible_for_final",
        category=Category.LEARNING,
        variables=("course_title",),
        subject="Final test unlocked for ${course_title}",
        body="Hello ${first_name},\n\nYou have completed everything required in ${course_title}. Your final test is now available."
        + _FOOTER,
    ),
    NotificationType(
        key="course_request.rejected",
        category=Category.SUBSCRIPTION,
        variables=("course_title", "reason"),
        subject="Your request for ${course_title} was not approved",
        body="Hello ${first_name},\n\nYour institution's request for ${course_title} was not approved.\nReason: ${reason}" + _FOOTER,
    ),
    NotificationType(
        key="subscription.activated",
        category=Category.SUBSCRIPTION,
        variables=("course_title", "seats", "ends_on"),
        subject="${course_title} is now active for your institution",
        body="Hello ${first_name},\n\nYour subscription to ${course_title} is active with ${seats} seats until ${ends_on}. You can now create batches and enrol students."
        + _FOOTER,
    ),
    NotificationType(
        key="subscription.cancelled",
        category=Category.SUBSCRIPTION,
        variables=("course_title", "reason"),
        subject="Your subscription to ${course_title} was cancelled",
        body="Hello ${first_name},\n\nYour institution's subscription to ${course_title} was cancelled.\nReason: ${reason}" + _FOOTER,
    ),
    NotificationType(
        key="subscription.expired",
        category=Category.SUBSCRIPTION,
        variables=("course_title",),
        subject="Your subscription to ${course_title} has expired",
        body="Hello ${first_name},\n\nYour institution's subscription to ${course_title} has expired. Request a renewal to keep access."
        + _FOOTER,
    ),
)

NOTIFICATION_TYPES: dict[str, NotificationType] = {notification_type.key: notification_type for notification_type in _TYPES}


@dataclass(frozen=True, slots=True)
class CategoryInfo:
    category: Category
    label: str
    email_editable: bool  # False: operational notices that are always emailed


CATEGORIES: tuple[CategoryInfo, ...] = (
    CategoryInfo(Category.ENROLLMENT, "Enrolments", email_editable=True),
    CategoryInfo(Category.LEARNING, "Learning progress", email_editable=True),
    CategoryInfo(Category.SUBSCRIPTION, "Subscriptions and course requests", email_editable=False),
)
CATEGORY_INFO: dict[Category, CategoryInfo] = {info.category: info for info in CATEGORIES}
