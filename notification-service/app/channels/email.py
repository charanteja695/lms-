import logging
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from html import escape
from typing import Protocol

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: str
    subject: str
    text_body: str
    html_body: str | None = None


class EmailSender(Protocol):
    """Raises on failure so the delivery is retried; returns normally only once the message was accepted."""

    async def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    """Development only: writes emails to the log. Refused in staging/production by Settings."""

    async def send(self, message: EmailMessage) -> None:
        logger.warning(
            "Email not sent (console backend)",
            extra={"extra_fields": {"to": message.to, "subject": message.subject, "body": message.text_body}},
        )


class SmtpEmailSender:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, message: EmailMessage) -> None:
        import aiosmtplib

        mime = MimeMessage()
        mime["From"] = self.settings.EMAIL_FROM
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text_body)
        if message.html_body:
            mime.add_alternative(message.html_body, subtype="html")

        password = self.settings.SMTP_PASSWORD.get_secret_value() if self.settings.SMTP_PASSWORD else None
        await aiosmtplib.send(
            mime,
            hostname=self.settings.SMTP_HOST,
            port=self.settings.SMTP_PORT,
            username=self.settings.SMTP_USERNAME,
            password=password,
            start_tls=self.settings.SMTP_STARTTLS,
            use_tls=self.settings.SMTP_USE_TLS,
            timeout=self.settings.SMTP_TIMEOUT_SECONDS,
        )


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.EMAIL_BACKEND == "smtp":
        return SmtpEmailSender(settings)
    return ConsoleEmailSender()


def html_from_text(body: str) -> str:
    """Minimal HTML alternative: every value was already rendered into ``body``, so escape it all."""
    paragraphs = "".join(f"<p>{escape(part).replace(chr(10), '<br>')}</p>" for part in body.split("\n\n") if part.strip())
    return f"<!doctype html><html><body>{paragraphs}</body></html>"
