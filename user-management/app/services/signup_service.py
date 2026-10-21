"""Self sign-up for individual learners: email + password → a code by email → the account, signed in.

Every self-registered learner is a student of one platform organisation, "Individual learners" (institution type
``individual``, created on the first sign-up and owned by the super admin), so the whole student experience works
for them unchanged. What they may study is what they buy (billing-service → subscription-service → learning-service).
"""

import re
import secrets
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.context import RequestContext
from app.core.exceptions import BadRequestError, ConflictError, PermissionDeniedError
from app.core.password_policy import ensure_strong_password
from app.core.security import constant_time_equals, generate_otp, hash_password, hash_token
from app.core.time import utcnow
from app.db.types import uuid7
from app.domain.enums import InstitutionType
from app.models.institution import Institution
from app.models.signup import SignupRequest
from app.models.user import User
from app.notifications.notifier import Notifier
from app.permissions.roles import OrganizationType, Role, UserStatus
from app.repositories.institution_repository import InstitutionRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditAction, AuditService
from app.services.rate_limiter import RateLimiter
from app.services.session_service import IssuedTokens, SessionService

INVALID_CODE = "The code is incorrect or has expired."
EMAIL_TAKEN = "An account already uses this email. Sign in, or reset your password."


class SignupService:
    def __init__(
        self, db: AsyncSession, settings: Settings, ctx: RequestContext, rate_limiter: RateLimiter, notifier: Notifier
    ) -> None:
        self.db = db
        self.settings = settings
        self.ctx = ctx
        self.rate_limiter = rate_limiter
        self.notifier = notifier
        self.users = UserRepository(db)
        self.institutions = InstitutionRepository(db)
        self.audit = AuditService(db, ctx)

    async def start(self, *, first_name: str, last_name: str, email: str, password: str) -> int:
        """Send a code to ``email``. Starting again (e.g. "resend") replaces any earlier code. Returns its lifetime (s)."""
        if not self.settings.SIGNUP_ENABLED:
            raise PermissionDeniedError(
                "Sign-up is closed. Ask your institution for an account.", code="SIGNUP_DISABLED"
            )
        email = email.strip().lower()
        await self.rate_limiter.hit(
            f"signup:email:{hash_token(email)}",
            limit=self.settings.SIGNUP_EMAIL_RATE_LIMIT_PER_HOUR,
            window_seconds=3600,
        )
        if await self.users.email_taken(email):
            raise ConflictError(EMAIL_TAKEN, code="EMAIL_TAKEN")
        ensure_strong_password(
            password, min_length=self.settings.PASSWORD_MIN_LENGTH, email=email, username=None, field="password"
        )

        now = utcnow()
        await self._close_open(email)
        otp = generate_otp(self.settings.OTP_LENGTH)
        self.db.add(
            SignupRequest(
                id=uuid7(),
                email=email,
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                password_hash=await hash_password(password),
                otp_hash=hash_token(otp),
                expires_at=now + timedelta(minutes=self.settings.OTP_EXPIRE_MINUTES),
                request_ip=self.ctx.ip_address,
            )
        )
        await self.db.commit()
        self.notifier.signup_code(email=email, name=first_name.strip(), otp=otp)
        return self.settings.OTP_EXPIRE_MINUTES * 60

    async def confirm(self, *, email: str, code: str) -> IssuedTokens:
        """A correct code creates the learner's account and signs them in."""
        email, now = email.strip().lower(), utcnow()
        request = (
            await self.db.execute(
                select(SignupRequest)
                .where(
                    SignupRequest.email == email, SignupRequest.consumed_at.is_(None), SignupRequest.expires_at > now
                )
                .order_by(SignupRequest.created_at.desc())
                .limit(1)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if request is None:
            raise BadRequestError(INVALID_CODE, code="INVALID_OTP")
        if not constant_time_equals(request.otp_hash, hash_token(code.strip())):
            request.attempts += 1
            if request.attempts >= self.settings.OTP_MAX_ATTEMPTS:
                request.consumed_at = now  # burn it: a new code must be requested
            await self.db.commit()
            raise BadRequestError(INVALID_CODE, code="INVALID_OTP")
        if await self.users.email_taken(email):  # someone else finished with this email meanwhile
            request.consumed_at = now
            await self.db.commit()
            raise ConflictError(EMAIL_TAKEN, code="EMAIL_TAKEN")

        request.consumed_at = now
        home = await self._individual_home()
        user = User(
            id=uuid7(),
            email=email,
            username=await self._username_for(email),
            password_hash=request.password_hash,
            first_name=request.first_name,
            last_name=request.last_name,
            role=Role.STUDENT,
            status=UserStatus.ACTIVE,
            institution_id=home.id,
            email_verified_at=now,
            password_changed_at=now,
            last_login_at=now,
        )
        self.users.add(user)
        await self.db.flush()
        self.audit.log(
            AuditAction.USER_CREATED,
            actor_id=user.id,
            resource_type="user",
            resource_id=user.id,
            institution_id=home.id,
            details={"role": user.role, "self_signup": True},
        )
        self.audit.event(
            "user.created",
            aggregate_type="user",
            aggregate_id=user.id,
            payload=self.users.event_payload(user, institution_public_id=home.public_id),
        )
        issued = await SessionService(self.db, self.settings).start(user, home, self.ctx, mfa_enabled=False)
        self.audit.log(
            AuditAction.LOGIN_SUCCEEDED,
            actor_id=user.id,
            institution_id=home.id,
            resource_type="user",
            resource_id=user.id,
        )
        await self.db.commit()
        return issued

    # ------------------------------------------------------------------ helpers

    async def _close_open(self, email: str) -> None:
        await self.db.execute(
            update(SignupRequest)
            .where(SignupRequest.email == email, SignupRequest.consumed_at.is_(None))
            .values(consumed_at=utcnow())
        )

    async def _username_for(self, email: str) -> str:
        base = re.sub(r"[^a-z0-9._]", "", email.split("@", 1)[0].lower())[:30] or "learner"
        candidate = base
        while await self.users.username_taken(candidate):
            candidate = f"{base}{secrets.randbelow(90000) + 10000}"
        return candidate

    async def _individual_home(self) -> Institution:
        """The "Individual learners" organisation; made on the first sign-up, owned by the (first) super admin."""
        home = (
            (
                await self.db.execute(
                    select(Institution).where(
                        Institution.institution_type == InstitutionType.INDIVIDUAL, Institution.deleted_at.is_(None)
                    )
                )
            )
            .scalars()
            .first()
        )
        if home is not None:
            return home
        owner = (
            await self.db.execute(
                select(User)
                .where(User.role == Role.SUPER_ADMIN, User.deleted_at.is_(None))
                .order_by(User.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()
        if owner is None:
            raise PermissionDeniedError("Sign-up is not available yet.", code="SIGNUP_DISABLED")
        s = self.settings
        home = Institution(
            id=uuid7(),
            name=s.INDIVIDUAL_ORG_NAME,
            code=s.INDIVIDUAL_ORG_CODE.upper(),
            org_type=OrganizationType.INSTITUTION,
            institution_type=InstitutionType.INDIVIDUAL,
            admin_id=owner.id,
            email=s.INDIVIDUAL_ORG_EMAIL,
            phone=s.INDIVIDUAL_ORG_PHONE,
            address_line1=s.INDIVIDUAL_ORG_ADDRESS,
            city=s.INDIVIDUAL_ORG_CITY,
            state=s.INDIVIDUAL_ORG_STATE,
            postal_code=s.INDIVIDUAL_ORG_POSTAL_CODE,
            country=s.DEFAULT_COUNTRY_CODE,
            timezone=s.DEFAULT_TIMEZONE,
            created_by_id=owner.id,
        )
        self.institutions.add(home)
        await self.db.flush()
        self.audit.event(
            "institution.created",
            aggregate_type="institution",
            aggregate_id=home.id,
            payload=self.institutions.event_payload(home, admin_public_id=owner.public_id),
        )
        return home
