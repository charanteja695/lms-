"""Renders and validates notification templates (``string.Template`` syntax, ``${name}``).

Rendering never fails: an unknown placeholder is left as written so a bad template is visible in
the output instead of breaking delivery. Validation is what keeps bad templates out — a super
admin can only save wording whose placeholders the notification type actually provides.
"""

from string import Template

from app.core.exceptions import ValidationFailedError
from app.domain.notification_types import NotificationType


def render(template: str, variables: dict[str, str]) -> str:
    return Template(template).safe_substitute(variables)


def _placeholders(template: str) -> tuple[set[str], bool]:
    """Return ``(names, is_well_formed)``. A stray ``$`` makes a template ill-formed."""
    template_obj = Template(template)
    if not template_obj.is_valid():
        return set(), False
    return {name for name in template_obj.get_identifiers()}, True


def validate_template(notification_type: NotificationType, *, subject: str, body: str) -> None:
    details: list[dict[str, str]] = []
    for field, value in (("subject", subject), ("body", body)):
        names, well_formed = _placeholders(value)
        if not well_formed:
            details.append(
                {
                    "field": field,
                    "code": "INVALID_TEMPLATE",
                    "message": "Use ${name} for placeholders and $$ for a literal dollar sign",
                }
            )
            continue
        unknown = sorted(names - notification_type.allowed_variables)
        if unknown:
            details.append(
                {
                    "field": field,
                    "code": "UNKNOWN_PLACEHOLDER",
                    "message": f"Unknown placeholder(s): {', '.join(unknown)}. "
                    f"Allowed: {', '.join(sorted(notification_type.allowed_variables))}",
                }
            )
    if details:
        raise ValidationFailedError(details=details)
