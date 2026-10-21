"""Import every model here so Base.metadata (and Alembic) sees all tables."""

from app.db.base import Base
from app.models.academics import ClassSection, Department, Program
from app.models.audit_log import AuditLog
from app.models.institution import Institution
from app.models.job import BackgroundJob, JobStatus, JobType
from app.models.mfa import MfaChallenge, MfaRecoveryCode, UserMfa
from app.models.outbox_event import OutboxEvent
from app.models.password_reset import PasswordResetPurpose, PasswordResetRequest
from app.models.permission import RolePermission, UserPermission
from app.models.profiles import EmploymentProfile, StudentGuardian, StudentProfile, UserProfile
from app.models.session import RefreshToken, UserSession
from app.models.signup import SignupRequest
from app.models.user import User

__all__ = [
    "AuditLog",
    "BackgroundJob",
    "Base",
    "ClassSection",
    "Department",
    "EmploymentProfile",
    "Institution",
    "JobStatus",
    "JobType",
    "MfaChallenge",
    "MfaRecoveryCode",
    "OutboxEvent",
    "PasswordResetPurpose",
    "PasswordResetRequest",
    "Program",
    "RefreshToken",
    "RolePermission",
    "SignupRequest",
    "StudentGuardian",
    "StudentProfile",
    "User",
    "UserMfa",
    "UserPermission",
    "UserProfile",
    "UserSession",
]
