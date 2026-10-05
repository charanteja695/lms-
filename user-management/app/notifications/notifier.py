import logging

from fastapi import BackgroundTasks

from app.core.config import Settings
from app.models.user import User
from app.notifications import templates
from app.notifications.email import EmailMessage, EmailSender

logger = logging.getLogger(__name__)


class Notifier:
    """Queues emails to be sent after the response, so delivery time never leaks account existence."""

    def __init__(self, background_tasks: BackgroundTasks | None, sender: EmailSender, settings: Settings) -> None:
        """``background_tasks`` is None outside a request (the worker): call ``flush()`` to send."""
        self._background_tasks = background_tasks
        self._sender = sender
        self._settings = settings
        self._pending: list[EmailMessage] = []

    def _queue(self, message: EmailMessage) -> None:
        if not message.to:  # e.g. students without an email address
            return
        if self._background_tasks is None:
            self._pending.append(message)
        else:
            self._background_tasks.add_task(self._deliver, message)

    async def flush(self) -> None:
        pending, self._pending = self._pending, []
        for message in pending:
            await self._deliver(message)

    async def _deliver(self, message: EmailMessage) -> None:
        try:
            await self._sender.send(message)
        except Exception:
            logger.exception("Failed to send email", extra={"extra_fields": {"subject": message.subject}})

    def password_reset(self, user: User, *, otp: str, link_token: str) -> None:
        link = f"{self._settings.frontend_url(self._settings.FRONTEND_RESET_PASSWORD_PATH)}?token={link_token}"
        self._queue(
            templates.password_reset_email(
                to=user.email or "",
                name=user.first_name,
                otp=otp,
                reset_link=link,
                expires_minutes=self._settings.OTP_EXPIRE_MINUTES,
            )
        )

    def account_setup(self, user: User, *, link_token: str) -> None:
        link = f"{self._settings.frontend_url(self._settings.FRONTEND_ACCOUNT_SETUP_PATH)}?token={link_token}"
        self._queue(
            templates.account_setup_email(
                to=user.email or "",
                name=user.first_name,
                username=user.username,
                setup_link=link,
                expires_hours=self._settings.ACCOUNT_SETUP_EXPIRE_HOURS,
            )
        )

    def account_created(self, user: User) -> None:
        self._queue(
            templates.account_created_email(
                to=user.email or "",
                name=user.first_name,
                username=user.username,
                login_link=self._settings.frontend_url(self._settings.FRONTEND_LOGIN_PATH),
            )
        )

    def export_ready(self, user: User, *, job_id: int, row_count: int, expires_hours: int) -> None:
        link = f"{self._settings.frontend_url(self._settings.FRONTEND_JOBS_PATH)}/{job_id}"
        self._queue(
            templates.export_ready_email(
                to=user.email or "", name=user.first_name, row_count=row_count, link=link, expires_hours=expires_hours
            )
        )

    def import_finished(self, user: User, *, job_id: int, summary: str, expires_hours: int) -> None:
        link = f"{self._settings.frontend_url(self._settings.FRONTEND_JOBS_PATH)}/{job_id}"
        self._queue(
            templates.import_finished_email(
                to=user.email or "", name=user.first_name, summary=summary, link=link, expires_hours=expires_hours
            )
        )

    def password_changed(self, user: User) -> None:
        self._queue(templates.password_changed_email(to=user.email or "", name=user.first_name))
