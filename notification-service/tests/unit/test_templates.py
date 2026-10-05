import pytest

from app.core.exceptions import ValidationFailedError
from app.domain.notification_types import NOTIFICATION_TYPES
from app.templates.renderer import render, validate_template


def test_render_fills_placeholders_and_leaves_unknown_ones_visible() -> None:
    assert render("Hi ${first_name}, see ${nothing}", {"first_name": "Asha"}) == "Hi Asha, see ${nothing}"


def test_render_never_executes_or_reads_attributes() -> None:
    assert render("${first_name.__class__}", {"first_name": "Asha"}) == "${first_name.__class__}"


def test_every_default_template_uses_only_its_own_placeholders() -> None:
    for notification_type in NOTIFICATION_TYPES.values():
        validate_template(notification_type, subject=notification_type.subject, body=notification_type.body)


def test_unknown_placeholder_is_rejected_with_the_field_named() -> None:
    with pytest.raises(ValidationFailedError) as caught:
        validate_template(NOTIFICATION_TYPES["enrollment.created"], subject="Hi ${nope}", body="ok ${course_title}")
    assert [(d["field"], d["code"]) for d in caught.value.details] == [("subject", "UNKNOWN_PLACEHOLDER")]


def test_placeholder_from_another_type_is_rejected() -> None:
    with pytest.raises(ValidationFailedError):
        validate_template(NOTIFICATION_TYPES["enrollment.created"], subject="s", body="Ends ${ends_on}")


def test_stray_dollar_sign_is_rejected_as_malformed() -> None:
    with pytest.raises(ValidationFailedError) as caught:
        validate_template(NOTIFICATION_TYPES["enrollment.created"], subject="Cost $5", body="ok")
    assert caught.value.details[0]["code"] == "INVALID_TEMPLATE"
