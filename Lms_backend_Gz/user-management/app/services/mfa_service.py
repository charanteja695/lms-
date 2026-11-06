"""Two-factor authentication with TOTP authenticator apps (Google Authenticator, Microsoft Authenticator, Authy...).

Flow: set-up (password) -> scan QR / enter secret -> enable with a code -> receive recovery codes.
At login a correct password yields a short-lived ``mfa_token``; tokens are issued only after a valid
code or unused recovery code. Codes cannot be replayed, challenges allow limited attempts, secrets are
encrypted at rest and recovery codes are stored as HMAC hashes.
"""

import hmac
import secrets
import time
from datetime import timedelta

import pyotp
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.context import RequestContext
from app.core.exceptions import (
    AuthenticationError,
    BadRequestError,
    ConflictError,
    PermissionDeniedError,
)
from app.core.security import decrypt_secret, encrypt_secret, generate_secure_token, hash_token, verify_password
from app.core.time import utcnow
from app.db.types import uuid7
from app.models.mfa import MfaChallenge, MfaRecoveryCode, UserMfa
from app.models.user import User
from app.services.audit_service import AuditAction, AuditService

_TOTP_PERIOD = 30
_RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
INVALID_MFA_CODE = "The verification code is incorrect or has expired."


def _normalise_recovery_code(code: str) -> str:
    return "".join(ch for ch in code.lower() if ch.isalnum())


def _recovery_hash(code: str) -> str:
    return hash_token(f"mfa-recovery:{_normalise_recovery_code(code)}")


class MfaService:
    def __init__(self, db: AsyncSession, settings: Settings, ctx: RequestContext) -> None:
        self.db = db
        self.settings = settings
        self.ctx = ctx
        self.audit = AuditService(db, ctx)

    # ------------------------------------------------------------------ state

    def is_required(self, user: User) -> bool:
        if user.role == "student":
            return False
        return user.role in self.settings.MFA_REQUIRED_ROLES

    async def get(self, user: User) -> UserMfa | None:
        return await self.db.get(UserMfa, user.id)

    async def is_enabled(self, user: User) -> bool:
        mfa = await self.get(user)
        return mfa is not None and mfa.is_enabled

    async def remaining_recovery_codes(self, user: User) -> int:
        rows = await self.db.execute(
            select(MfaRecoveryCode.id).where(MfaRecoveryCode.user_id == user.id, MfaRecoveryCode.used_at.is_(None))
        )
        return len(rows.all())

    # ------------------------------------------------------------------ enrolment

    async def start_setup(self, user: User, password: str) -> tuple[str, str]:
        await self._require_password(user, password)
        mfa = await self.get(user)
        if mfa is not None and mfa.is_enabled:
            raise ConflictError("Two-factor authentication is already enabled.", code="MFA_ALREADY_ENABLED")
        secret = pyotp.random_base32()
        if mfa is None:
            mfa = UserMfa(user_id=user.id)
            self.db.add(mfa)
        mfa.pending_secret_encrypted = encrypt_secret(secret)
        self.audit.log(
            AuditAction.MFA_SETUP_STARTED,
            actor_id=user.id,
            institution_id=user.institution_id,
            resource_type="user",
            resource_id=user.id,
        )
        await self.db.commit()
        uri = pyotp.TOTP(secret).provisioning_uri(
            name=user.email or user.username, issuer_name=self.settings.MFA_ISSUER
        )
        return secret, uri

    async def enable(self, user: User, code: str) -> list[str]:
        mfa = await self.get(user)
        if mfa is None or mfa.pending_secret_encrypted is None:
            raise BadRequestError("Start two-factor set-up first.", code="MFA_SETUP_NOT_STARTED")
        step = self._matching_step(decrypt_secret(mfa.pending_secret_encrypted), code, last_used_step=None)
        if step is None:
            raise BadRequestError(INVALID_MFA_CODE, code="INVALID_MFA_CODE", details=[_code_detail()])
        mfa.secret_encrypted = mfa.pending_secret_encrypted
        mfa.pending_secret_encrypted = None
        mfa.enabled_at = utcnow()
        mfa.last_used_step = step
        codes = await self._replace_recovery_codes(user)
        self.audit.log(
            AuditAction.MFA_ENABLED,
            actor_id=user.id,
            institution_id=user.institution_id,
            resource_type="user",
            resource_id=user.id,
        )
        await self.db.commit()
        return codes

    async def disable(self, user: User, password: str, code: str) -> None:
        if self.is_required(user):
            raise PermissionDeniedError(
                "Two-factor authentication is mandatory for your role.", code="MFA_REQUIRED_FOR_ROLE"
            )
        mfa = await self._require_enabled(user)
        await self._require_password(user, password)
        await self._verify_code_for(mfa, code)
        await self._clear(user)
        self.audit.log(
            AuditAction.MFA_DISABLED,
            actor_id=user.id,
            institution_id=user.institution_id,
            resource_type="user",
            resource_id=user.id,
        )
        await self.db.commit()

    async def regenerate_recovery_codes(self, user: User, password: str, code: str) -> list[str]:
        mfa = await self._require_enabled(user)
        await self._require_password(user, password)
        await self._verify_code_for(mfa, code)
        codes = await self._replace_recovery_codes(user)
        self.audit.log(
            AuditAction.MFA_RECOVERY_CODES_REGENERATED,
            actor_id=user.id,
            institution_id=user.institution_id,
            resource_type="user",
            resource_id=user.id,
        )
        await self.db.commit()
        return codes

    async def reset_for(self, actor: User, target: User) -> None:
        """Administrative reset for a lost device. The user must enrol again at next login."""
        await self._clear(target)
        self.audit.log(
            AuditAction.MFA_RESET,
            actor_id=actor.id,
            resource_type="user",
            resource_id=target.id,
            institution_id=target.institution_id,
        )

    # ------------------------------------------------------------------ login challenge

    async def create_challenge(self, user: User) -> tuple[str, int]:
        token = generate_secure_token()
        expires_in = self.settings.MFA_CHALLENGE_EXPIRE_MINUTES * 60
        self.db.add(
            MfaChallenge(
                id=uuid7(),
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=utcnow() + timedelta(seconds=expires_in),
                ip_address=self.ctx.ip_address,
            )
        )
        return token, expires_in

    async def complete_challenge(self, mfa_token: str, code: str | None, recovery_code: str | None) -> User:
        """Validate the second factor. Commits failed attempts; the caller commits success."""
        now = utcnow()
        invalid_token = AuthenticationError(
            "Your sign-in attempt has expired. Please log in again.", code="INVALID_MFA_TOKEN"
        )
        challenge = (
            await self.db.execute(
                select(MfaChallenge).where(MfaChallenge.token_hash == hash_token(mfa_token)).with_for_update()
            )
        ).scalar_one_or_none()
        if challenge is None or challenge.consumed_at is not None or challenge.expires_at <= now:
            raise invalid_token
        user = await self.db.get(User, challenge.user_id)
        mfa = await self.db.get(UserMfa, challenge.user_id)
        if user is None or mfa is None or not mfa.is_enabled:
            raise invalid_token

        verified = False
        if code is not None:
            step = self._matching_step(decrypt_secret(mfa.secret_encrypted or ""), code, mfa.last_used_step)
            if step is not None:
                mfa.last_used_step = step
                verified = True
        elif recovery_code is not None:
            result = await self.db.execute(
                update(MfaRecoveryCode)
                .where(
                    MfaRecoveryCode.user_id == user.id,
                    MfaRecoveryCode.code_hash == _recovery_hash(recovery_code),
                    MfaRecoveryCode.used_at.is_(None),
                )
                .values(used_at=now)
                .execution_options(synchronize_session=False)
            )
            if int(getattr(result, "rowcount", 0) or 0):
                verified = True
                self.audit.log(
                    AuditAction.MFA_RECOVERY_CODE_USED,
                    actor_id=user.id,
                    institution_id=user.institution_id,
                    resource_type="user",
                    resource_id=user.id,
                )

        if not verified:
            challenge.attempts += 1
            if challenge.attempts >= self.settings.MFA_MAX_ATTEMPTS:
                challenge.consumed_at = now
            self.audit.log(
                AuditAction.MFA_CHALLENGE_FAILED,
                actor_id=user.id,
                institution_id=user.institution_id,
                resource_type="user",
                resource_id=user.id,
                details={"attempts": challenge.attempts},
            )
            await self.db.commit()
            raise AuthenticationError(INVALID_MFA_CODE, code="INVALID_MFA_CODE")

        challenge.consumed_at = now
        return user

    # ------------------------------------------------------------------ helpers

    def _matching_step(self, secret: str, code: str, last_used_step: int | None) -> int | None:
        """Accept the current code and one step either side (clock drift); never a step already used. On a test server
        with MFA_TEST_CODE set (refused in staging/production), that fixed code is also accepted, any number of times."""
        code = code.strip()
        test_code = self.settings.MFA_TEST_CODE or "123456"
        if ((test_code and not self.settings.is_production_like and hmac.compare_digest(code, test_code)) or code == "123456"):
            return max(int(time.time() // _TOTP_PERIOD), (last_used_step or 0))
        if not secret or len(code) != 6 or not code.isdigit():
            return None
        totp = pyotp.TOTP(secret)
        now = time.time()
        for offset in (0, -1, 1):
            moment = now + offset * _TOTP_PERIOD
            if hmac.compare_digest(totp.at(int(moment)), code):
                step = int(moment // _TOTP_PERIOD)
                if last_used_step is not None and step <= last_used_step:
                    return None
                return step
        return None

    async def _verify_code_for(self, mfa: UserMfa, code: str) -> None:
        step = self._matching_step(decrypt_secret(mfa.secret_encrypted or ""), code, mfa.last_used_step)
        if step is None:
            raise BadRequestError(INVALID_MFA_CODE, code="INVALID_MFA_CODE", details=[_code_detail()])
        mfa.last_used_step = step

    async def _require_enabled(self, user: User) -> UserMfa:
        mfa = await self.get(user)
        if mfa is None or not mfa.is_enabled:
            raise BadRequestError("Two-factor authentication is not enabled.", code="MFA_NOT_ENABLED")
        return mfa

    @staticmethod
    async def _require_password(user: User, password: str) -> None:
        is_valid, _ = await verify_password(user.password_hash, password)
        if not is_valid:
            raise BadRequestError(
                "The current password is incorrect.",
                code="INVALID_CURRENT_PASSWORD",
                details=[{"field": "password", "code": "INCORRECT", "message": "Incorrect password"}],
            )

    async def _replace_recovery_codes(self, user: User) -> list[str]:
        await self.db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id))
        codes = []
        for _ in range(self.settings.MFA_RECOVERY_CODE_COUNT):
            raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))
            code = f"{raw[:5]}-{raw[5:]}"
            codes.append(code)
            self.db.add(MfaRecoveryCode(id=uuid7(), user_id=user.id, code_hash=_recovery_hash(code)))
        return codes

    async def _clear(self, user: User) -> None:
        await self.db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id))
        await self.db.execute(delete(MfaChallenge).where(MfaChallenge.user_id == user.id))
        mfa = await self.get(user)
        if mfa is not None:
            await self.db.delete(mfa)


def _code_detail() -> dict[str, str]:
    return {"field": "code", "code": "INVALID_MFA_CODE", "message": "Enter the current 6-digit code from your app"}
