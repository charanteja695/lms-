import logging
import uuid
from enum import StrEnum
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.db.types import uuid7
from app.models.audit_log import AuditLog
from app.models.outbox_event import OutboxEvent
from app.repositories.audit_repository import AuditRepository

logger = logging.getLogger("audit")


class AuditAction(StrEnum):
    LOGIN_SUCCEEDED = "auth.login_succeeded"
    LOGIN_FAILED = "auth.login_failed"
    ACCOUNT_LOCKED = "auth.account_locked"
    LOGOUT = "auth.logout"
    TOKEN_REFRESHED = "auth.token_refreshed"
    REFRESH_TOKEN_REUSE = "auth.refresh_token_reuse_detected"
    PASSWORD_RESET_REQUESTED = "auth.password_reset_requested"
    PASSWORD_RESET_OTP_FAILED = "auth.password_reset_otp_failed"
    PASSWORD_RESET_OTP_VERIFIED = "auth.password_reset_otp_verified"
    PASSWORD_RESET_COMPLETED = "auth.password_reset_completed"
    PASSWORD_CHANGED = "auth.password_changed"
    MFA_SETUP_STARTED = "auth.mfa_setup_started"
    MFA_ENABLED = "auth.mfa_enabled"
    MFA_DISABLED = "auth.mfa_disabled"
    MFA_RESET = "auth.mfa_reset"
    MFA_RECOVERY_CODES_REGENERATED = "auth.mfa_recovery_codes_regenerated"
    MFA_RECOVERY_CODE_USED = "auth.mfa_recovery_code_used"
    MFA_CHALLENGE_FAILED = "auth.mfa_challenge_failed"

    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_STATUS_CHANGED = "user.status_changed"
    USER_DELETED = "user.deleted"
    USER_ACCESS_REVOKED = "user.access_revoked"
    USER_PASSWORD_SET = "user.password_set"
    USERS_EXPORTED = "user.exported"
    USERS_IMPORTED = "user.imported"
    EXPORT_JOB_CREATED = "job.export_created"
    IMPORT_JOB_CREATED = "job.import_created"
    EXPORT_DOWNLOADED = "job.export_downloaded"

    INSTITUTION_CREATED = "institution.created"
    INSTITUTION_UPDATED = "institution.updated"
    INSTITUTION_STATUS_CHANGED = "institution.status_changed"
    INSTITUTION_DELETED = "institution.deleted"
    INSTITUTION_ACCESS_REVOKED = "institution.access_revoked"
    INSTITUTIONS_EXPORTED = "institution.exported"

    EMPLOYER_CREATED = "employer.created"
    EMPLOYER_UPDATED = "employer.updated"
    EMPLOYER_STATUS_CHANGED = "employer.status_changed"
    EMPLOYER_DELETED = "employer.deleted"
    EMPLOYER_ACCESS_REVOKED = "employer.access_revoked"
    EMPLOYERS_EXPORTED = "employer.exported"


class AuditService:
    """Writes audit records and outbox events into the caller's transaction."""

    def __init__(self, db: AsyncSession, ctx: RequestContext) -> None:
        self.repo = AuditRepository(db)
        self.ctx = ctx

    def log(
        self,
        action: AuditAction,
        *,
        actor_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        institution_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.repo.add_log(
            AuditLog(
                id=uuid7(),
                actor_id=actor_id,
                action=action.value,
                resource_type=resource_type,
                resource_id=resource_id,
                institution_id=institution_id,
                ip_address=self.ctx.ip_address,
                user_agent=self.ctx.user_agent,
                request_id=self.ctx.request_id,
                details=jsonable_encoder(details) if details else None,
            )
        )
        logger.info(
            action.value,
            extra={
                "extra_fields": {
                    "audit_action": action.value,
                    "actor_id": actor_id,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "ip": self.ctx.ip_address,
                }
            },
        )

    def event(self, event_type: str, *, aggregate_type: str, aggregate_id: uuid.UUID, payload: dict[str, Any]) -> None:
        self.repo.add_event(
            OutboxEvent(
                id=uuid7(),
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload=jsonable_encoder(payload),
            )
        )
