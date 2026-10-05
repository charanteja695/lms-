"""Login, token refresh, logout, device sessions and the password flows."""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.context import RequestContext
from app.core.exceptions import (
    AppError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.core.password_policy import ensure_strong_password
from app.core.security import (
    constant_time_equals,
    generate_otp,
    generate_secure_token,
    hash_password,
    hash_token,
    spend_password_verification_time,
    verify_password,
)
from app.core.time import utcnow
from app.db.types import uuid7
from app.models.password_reset import PasswordResetPurpose, PasswordResetRequest
from app.models.session import UserSession
from app.models.user import User
from app.notifications.notifier import Notifier
from app.permissions.roles import UserStatus
from app.repositories.institution_repository import InstitutionRepository
from app.repositories.password_reset_repository import PasswordResetRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import MfaChallengeOut, PasswordResetTokenOut
from app.services.access_service import ensure_institution_access, ensure_user_active
from app.services.audit_service import AuditAction, AuditService
from app.services.mfa_service import MfaService
from app.services.rate_limiter import RateLimiter
from app.services.session_service import IssuedTokens, RevokeReason, SessionService

INVALID_CREDENTIALS = "The email/username or password is incorrect."
INVALID_REFRESH_TOKEN = "Your session has expired. Please log in again."
INVALID_OTP = "The code is incorrect or has expired."
INVALID_RESET_TOKEN = "This password reset link or token is invalid or has expired."


class AuthService:
    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        ctx: RequestContext,
        rate_limiter: RateLimiter,
        notifier: Notifier,
    ) -> None:
        self.db = db
        self.settings = settings
        self.ctx = ctx
        self.rate_limiter = rate_limiter
        self.notifier = notifier
        self.users = UserRepository(db)
        self.institutions = InstitutionRepository(db)
        self.session_repo = SessionRepository(db)
        self.resets = PasswordResetRepository(db)
        self.sessions = SessionService(db, settings)
        self.audit = AuditService(db, ctx)
        self.mfa = MfaService(db, settings, ctx)

    # ------------------------------------------------------------------ login

    async def login(self, identifier: str, password: str) -> IssuedTokens | MfaChallengeOut:
        now = utcnow()
        user = await self.users.get_by_identifier(identifier)

        if user is None:
            await spend_password_verification_time(password)
            self.audit.log(AuditAction.LOGIN_FAILED, details={"reason": "unknown_identifier"})
            await self.db.commit()
            raise AuthenticationError(INVALID_CREDENTIALS, code="INVALID_CREDENTIALS")

        if user.locked_until is not None and user.locked_until > now:
            await spend_password_verification_time(password)
            self.audit.log(
                AuditAction.LOGIN_FAILED,
                actor_id=user.id,
                institution_id=user.institution_id,
                details={"reason": "locked"},
            )
            await self.db.commit()
            raise self._locked_error(int((user.locked_until - now).total_seconds()))

        if user.password_hash.startswith("!"):  # account set-up not completed: no password exists yet
            await spend_password_verification_time(password)
            is_valid, needs_rehash = False, False
        else:
            is_valid, needs_rehash = await verify_password(user.password_hash, password)
        if not is_valid:
            await self._record_failed_login(user)
            raise AuthenticationError(INVALID_CREDENTIALS, code="INVALID_CREDENTIALS")

        # Status is only revealed to someone who knows the password.
        try:
            ensure_user_active(user)
            institution = await ensure_institution_access(user, self.institutions)
        except PermissionDeniedError as exc:
            self.audit.log(
                AuditAction.LOGIN_FAILED,
                actor_id=user.id,
                institution_id=user.institution_id,
                details={"reason": exc.code},
            )
            await self.db.commit()
            raise

        if needs_rehash:
            user.password_hash = await hash_password(password)
        user.failed_login_attempts = 0
        user.locked_until = None

        if await self.mfa.is_enabled(user):
            # Password was right; tokens are only issued after the second factor.
            mfa_token, expires_in = await self.mfa.create_challenge(user)
            await self.db.commit()
            return MfaChallengeOut(mfa_token=mfa_token, expires_in=expires_in)

        user.last_login_at = now
        issued = await self.sessions.start(user, institution, self.ctx, mfa_enabled=False)
        self.audit.log(
            AuditAction.LOGIN_SUCCEEDED,
            actor_id=user.id,
            institution_id=user.institution_id,
            resource_type="user",
            resource_id=user.id,
        )
        await self.db.commit()
        return issued

    async def verify_mfa(self, mfa_token: str, code: str | None, recovery_code: str | None) -> IssuedTokens:
        user = await self.mfa.complete_challenge(mfa_token, code, recovery_code)
        try:
            ensure_user_active(user)
            institution = await ensure_institution_access(user, self.institutions)
        except PermissionDeniedError:
            await self.db.commit()
            raise
        user.last_login_at = utcnow()
        issued = await self.sessions.start(user, institution, self.ctx, mfa_enabled=True)
        self.audit.log(
            AuditAction.LOGIN_SUCCEEDED,
            actor_id=user.id,
            institution_id=user.institution_id,
            resource_type="user",
            resource_id=user.id,
            details={"second_factor": "totp" if code else "recovery_code"},
        )
        await self.db.commit()
        return issued

    @staticmethod
    def _locked_error(retry_after_seconds: int) -> AuthenticationError:
        minutes = max(1, -(-retry_after_seconds // 60))
        return AuthenticationError(
            f"Too many failed attempts. Your account is locked for {minutes} more minute(s).",
            code="ACCOUNT_LOCKED",
            headers={"WWW-Authenticate": "Bearer", "Retry-After": str(max(retry_after_seconds, 1))},
        )

    async def _record_failed_login(self, user: User) -> None:
        attempts = await self.users.increment_failed_logins(user)
        self.audit.log(
            AuditAction.LOGIN_FAILED,
            actor_id=user.id,
            institution_id=user.institution_id,
            details={"reason": "bad_password"},
        )
        if attempts >= self.settings.MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = utcnow() + timedelta(minutes=self.settings.ACCOUNT_LOCKOUT_MINUTES)
            user.failed_login_attempts = 0
            self.audit.log(
                AuditAction.ACCOUNT_LOCKED,
                actor_id=user.id,
                institution_id=user.institution_id,
                resource_type="user",
                resource_id=user.id,
            )
        await self.db.commit()

    # ------------------------------------------------------------------ tokens & sessions

    async def refresh(self, raw_refresh_token: str) -> IssuedTokens:
        now = utcnow()
        invalid = AuthenticationError(INVALID_REFRESH_TOKEN, code="INVALID_REFRESH_TOKEN")
        token = await self.session_repo.get_refresh_token(hash_token(raw_refresh_token), for_update=True)
        if token is None:
            raise invalid
        session = await self.session_repo.get_session(token.session_id)
        if session is None:
            raise invalid

        if token.used_at is not None:
            # A rotated token came back: it was stolen or replayed. End the whole session.
            self.session_repo.revoke(session, reason=RevokeReason.REFRESH_REUSE, now=now)
            self.audit.log(
                AuditAction.REFRESH_TOKEN_REUSE,
                actor_id=session.user_id,
                resource_type="session",
                resource_id=session.id,
            )
            await self.db.commit()
            raise invalid

        if session.revoked_at is not None or session.expires_at <= now or token.expires_at <= now:
            raise invalid

        user = await self.users.get(session.user_id)
        try:
            if user is None:
                raise invalid
            ensure_user_active(user)
            institution = await ensure_institution_access(user, self.institutions)
        except AppError:
            self.session_repo.revoke(session, reason=RevokeReason.ACCOUNT_INACTIVE, now=now)
            await self.db.commit()
            raise

        token.used_at = now
        session.last_used_at = now
        session.ip_address = self.ctx.ip_address
        issued = self.sessions.issue_tokens(user, institution, session, mfa_enabled=await self.mfa.is_enabled(user))
        self.audit.log(
            AuditAction.TOKEN_REFRESHED,
            actor_id=user.id,
            institution_id=user.institution_id,
            resource_type="session",
            resource_id=session.id,
        )
        await self.db.commit()
        return issued

    async def logout(self, user: User, session: UserSession, *, all_sessions: bool) -> None:
        if all_sessions:
            await self.sessions.revoke_all_for_user(user, reason=RevokeReason.LOGOUT_ALL)
        else:
            self.session_repo.revoke(session, reason=RevokeReason.LOGOUT, now=utcnow())
        self.audit.log(
            AuditAction.LOGOUT,
            actor_id=user.id,
            institution_id=user.institution_id,
            resource_type="session",
            resource_id=session.id,
            details={"all_sessions": all_sessions},
        )
        await self.db.commit()

    async def list_sessions(self, user: User) -> list[UserSession]:
        return await self.session_repo.list_active_for_user(user.id, now=utcnow())

    async def end_session(self, user: User, session_public_id: int) -> None:
        """Sign out one of the user's own devices."""
        session = await self.session_repo.get_session_by_public_id(session_public_id)
        if session is None or session.user_id != user.id or session.revoked_at is not None:
            raise NotFoundError("Session not found.", code="SESSION_NOT_FOUND")
        self.session_repo.revoke(session, reason=RevokeReason.USER_SIGNED_OUT_DEVICE, now=utcnow())
        self.audit.log(
            AuditAction.LOGOUT,
            actor_id=user.id,
            institution_id=user.institution_id,
            resource_type="session",
            resource_id=session.id,
        )
        await self.db.commit()

    # ------------------------------------------------------------------ forgot / reset password

    async def forgot_password(self, identifier: str) -> None:
        """Always completes silently so callers cannot discover which accounts exist."""
        await self.rate_limiter.hit(
            f"forgot-password:identifier:{hash_token(identifier)}",
            limit=self.settings.FORGOT_PASSWORD_IDENTIFIER_RATE_LIMIT_PER_HOUR,
            window_seconds=3600,
        )
        user = await self.users.get_by_identifier(identifier)
        if user is None or user.status != UserStatus.ACTIVE or not user.email:
            # No email on file (students without email): their institution sets a new temporary password.
            self.audit.log(AuditAction.PASSWORD_RESET_REQUESTED, details={"delivered": False})
            await self.db.commit()
            return

        now = utcnow()
        await self.resets.consume_all_open(user.id, now=now)
        otp = generate_otp(self.settings.OTP_LENGTH)
        link_token = generate_secure_token()
        self.resets.add(
            PasswordResetRequest(
                id=uuid7(),
                user_id=user.id,
                purpose=PasswordResetPurpose.PASSWORD_RESET,
                otp_hash=hash_token(otp),
                link_token_hash=hash_token(link_token),
                expires_at=now + timedelta(minutes=self.settings.OTP_EXPIRE_MINUTES),
                request_ip=self.ctx.ip_address,
            )
        )
        self.audit.log(
            AuditAction.PASSWORD_RESET_REQUESTED,
            actor_id=user.id,
            institution_id=user.institution_id,
            resource_type="user",
            resource_id=user.id,
            details={"delivered": True},
        )
        await self.db.commit()
        self.notifier.password_reset(user, otp=otp, link_token=link_token)

    async def verify_otp(self, identifier: str, otp: str) -> PasswordResetTokenOut:
        now = utcnow()
        invalid = BadRequestError(INVALID_OTP, code="INVALID_OTP")
        user = await self.users.get_by_identifier(identifier)
        request = await self.resets.get_open_otp_request(user.id, now=now) if user else None
        if user is None or request is None or request.otp_hash is None:
            raise invalid

        if not constant_time_equals(request.otp_hash, hash_token(otp)):
            request.attempts += 1
            if request.attempts >= self.settings.OTP_MAX_ATTEMPTS:
                request.consumed_at = now  # burn the code; a new one must be requested
            self.audit.log(
                AuditAction.PASSWORD_RESET_OTP_FAILED,
                actor_id=user.id,
                institution_id=user.institution_id,
                resource_type="user",
                resource_id=user.id,
                details={"attempts": request.attempts},
            )
            await self.db.commit()
            raise invalid

        reset_token = generate_secure_token()
        expires_in = self.settings.RESET_TOKEN_EXPIRE_MINUTES * 60
        request.verified_at = now
        request.reset_token_hash = hash_token(reset_token)
        request.reset_token_expires_at = now + timedelta(seconds=expires_in)
        self.audit.log(
            AuditAction.PASSWORD_RESET_OTP_VERIFIED,
            actor_id=user.id,
            institution_id=user.institution_id,
            resource_type="user",
            resource_id=user.id,
        )
        await self.db.commit()
        return PasswordResetTokenOut(reset_token=reset_token, expires_in=expires_in)

    async def reset_password(self, raw_token: str, new_password: str) -> None:
        """Accepts the token returned by verify-otp or the token from an emailed reset / set-up link."""
        now = utcnow()
        invalid = BadRequestError(INVALID_RESET_TOKEN, code="INVALID_RESET_TOKEN")
        token_hash = hash_token(raw_token)
        request = await self.resets.get_by_token_hash(token_hash)
        if request is None or request.consumed_at is not None:
            raise invalid

        via_otp = request.reset_token_hash is not None and constant_time_equals(request.reset_token_hash, token_hash)
        if via_otp:
            is_live = request.reset_token_expires_at is not None and request.reset_token_expires_at > now
        else:
            is_live = request.verified_at is None and request.expires_at > now
        user = await self.users.get(request.user_id)
        if not is_live or user is None or user.status != UserStatus.ACTIVE:
            raise invalid

        await self._set_new_password(user, new_password)
        user.must_change_password = False
        user.failed_login_attempts = 0
        user.locked_until = None
        user.email_verified_at = user.email_verified_at or now  # receiving the email proves ownership
        await self.resets.consume_all_open(user.id, now=now)
        await self.sessions.revoke_all_for_user(user, reason=RevokeReason.PASSWORD_RESET)
        self.audit.log(
            AuditAction.PASSWORD_RESET_COMPLETED,
            actor_id=user.id,
            institution_id=user.institution_id,
            resource_type="user",
            resource_id=user.id,
            details={"purpose": request.purpose, "method": "otp" if via_otp else "link"},
        )
        await self.db.commit()
        self.notifier.password_changed(user)

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        now = utcnow()
        if user.locked_until is not None and user.locked_until > now:
            raise self._locked_error(int((user.locked_until - now).total_seconds()))
        is_valid, _ = await verify_password(user.password_hash, current_password)
        if not is_valid:
            await self._record_failed_login(user)
            raise BadRequestError(
                "The current password is incorrect.",
                code="INVALID_CURRENT_PASSWORD",
                details=[{"field": "current_password", "code": "INCORRECT", "message": "Incorrect password"}],
            )

        await self._set_new_password(user, new_password)
        user.must_change_password = False
        await self.sessions.revoke_all_for_user(user, reason=RevokeReason.PASSWORD_CHANGED)
        self.audit.log(
            AuditAction.PASSWORD_CHANGED,
            actor_id=user.id,
            institution_id=user.institution_id,
            resource_type="user",
            resource_id=user.id,
        )
        await self.db.commit()
        self.notifier.password_changed(user)

    async def _set_new_password(self, user: User, new_password: str) -> None:
        ensure_strong_password(
            new_password,
            min_length=self.settings.PASSWORD_MIN_LENGTH,
            email=user.email,
            username=user.username,
            field="new_password",
        )
        is_same, _ = await verify_password(user.password_hash, new_password)
        if is_same:
            raise ValidationFailedError(
                "Choose a password different from your current one.",
                code="PASSWORD_REUSED",
                details=[
                    {
                        "field": "new_password",
                        "code": "PASSWORD_REUSED",
                        "message": "Must differ from the current password",
                    }
                ],
            )
        user.password_hash = await hash_password(new_password)
        user.password_changed_at = utcnow()
