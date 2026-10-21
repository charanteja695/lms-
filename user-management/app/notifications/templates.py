from html import escape

from app.notifications.email import EmailMessage


def _html(paragraphs: list[str], link: tuple[str, str] | None = None) -> str:
    body = "".join(f"<p>{escape(p)}</p>" for p in paragraphs)
    if link:
        label, url = link
        body += f'<p><a href="{escape(url, quote=True)}">{escape(label)}</a></p>'
    return f"<!doctype html><html><body>{body}</body></html>"


def password_reset_email(*, to: str, name: str, otp: str, reset_link: str, expires_minutes: int) -> EmailMessage:
    lines = [
        f"Hello {name},",
        "We received a request to reset your LMS password.",
        f"Your one-time code is: {otp}",
        f"The code and the link below expire in {expires_minutes} minutes.",
        "If you did not request this, you can ignore this email; your password will not change.",
    ]
    return EmailMessage(
        to=to,
        subject="Reset your LMS password",
        text_body="\n\n".join([*lines, f"Reset link: {reset_link}"]),
        html_body=_html(lines, ("Reset password", reset_link)),
    )


def signup_code_email(*, to: str, name: str, otp: str, expires_minutes: int) -> EmailMessage:
    lines = [
        f"Hello {name},",
        "Welcome to LMS. Enter this code to confirm your email and finish creating your account:",
        f"Your one-time code is: {otp}",
        f"It expires in {expires_minutes} minutes. If you did not sign up, you can ignore this email.",
    ]
    return EmailMessage(to=to, subject="Your LMS sign-up code", text_body="\n\n".join(lines), html_body=_html(lines))


def account_setup_email(*, to: str, name: str, username: str, setup_link: str, expires_hours: int) -> EmailMessage:
    lines = [
        f"Hello {name},",
        "An LMS account has been created for you.",
        f"Username: {username}",
        f"Use the link below to set your password. It expires in {expires_hours} hours.",
    ]
    return EmailMessage(
        to=to,
        subject="Set up your LMS account",
        text_body="\n\n".join([*lines, f"Set-up link: {setup_link}"]),
        html_body=_html(lines, ("Set password", setup_link)),
    )


def account_created_email(*, to: str, name: str, username: str, login_link: str) -> EmailMessage:
    lines = [
        f"Hello {name},",
        "An LMS account has been created for you.",
        f"Username: {username}",
        "Your administrator will share your initial password. You will be asked to change it at first login.",
    ]
    return EmailMessage(
        to=to,
        subject="Your LMS account",
        text_body="\n\n".join([*lines, f"Login: {login_link}"]),
        html_body=_html(lines, ("Log in", login_link)),
    )


def password_changed_email(*, to: str, name: str) -> EmailMessage:
    lines = [
        f"Hello {name},",
        "Your LMS password was just changed and all your sessions were signed out.",
        "If this was not you, contact your administrator immediately.",
    ]
    return EmailMessage(
        to=to, subject="Your LMS password was changed", text_body="\n\n".join(lines), html_body=_html(lines)
    )


def import_finished_email(*, to: str, name: str, summary: str, link: str, expires_hours: int) -> EmailMessage:
    lines = [
        f"Hello {name},",
        f"Your user import has finished: {summary}.",
        f"Download the report within {expires_hours} hours. You will need to be logged in.",
    ]
    return EmailMessage(
        to=to,
        subject="Your LMS user import has finished",
        text_body="\n\n".join([*lines, f"Report: {link}"]),
        html_body=_html(lines, ("View report", link)),
    )


def export_ready_email(*, to: str, name: str, row_count: int, link: str, expires_hours: int) -> EmailMessage:
    lines = [
        f"Hello {name},",
        f"Your export is ready ({row_count:,} rows).",
        f"Download it within {expires_hours} hours. You will need to be logged in.",
    ]
    return EmailMessage(
        to=to,
        subject="Your LMS export is ready",
        text_body="\n\n".join([*lines, f"Download: {link}"]),
        html_body=_html(lines, ("Download export", link)),
    )
