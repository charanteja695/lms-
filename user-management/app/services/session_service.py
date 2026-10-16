import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.context import RequestContext
from app.core.security import create_access_token, generate_secure_token, hash_token
from app.core.time import utcnow
from app.db.types import uuid7
from app.models.institution import Institution
from app.models.session import RefreshToken, UserSession
from app.models.user import User
from app.permissions.roles import Role
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthUserOut, TokenOut
from app.schemas.summaries import InstitutionRef
from app.services.permission_service import PermissionService


class RevokeReason:
    LOGOUT = "logout"
    LOGOUT_ALL = "logout_all"
    USER_SIGNED_OUT_DEVICE = "user_signed_out_device"
    ADMIN_REVOKE = "admin_revoke"
    SUSPENDED = "suspended"
    DELETED = "deleted"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET = "password_reset"
    PASSWORD_SET_BY_MANAGER = "password_set_by_manager"
    ROLE_CHANGED = "role_or_institution_changed"
    REFRESH_REUSE = "refresh_token_reuse"
    ACCOUNT_INACTIVE = "account_inactive"
    INSTITUTION_REVOKE = "institution_revoke"
    INSTITUTION_SUSPENDED = "institution_suspended"
    INSTITUTION_DELETED = "institution_deleted"


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    token: TokenOut
    user: AuthUserOut


class SessionService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.repo = SessionRepository(db)
        self.users = UserRepository(db)

    async def start(
        self, user: User, institution: Institution | None, ctx: RequestContext, *, mfa_enabled: bool
    ) -> IssuedTokens:
        now = utcnow()
        session = UserSession(
            id=uuid7(),
            user_id=user.id,
            ip_address=ctx.ip_address,
            user_agent=ctx.user_agent,
            last_used_at=now,
            expires_at=now + timedelta(days=self.settings.SESSION_MAX_LIFETIME_DAYS),
        )
        self.repo.add(session)
        await self.db.flush()  # the refresh token row references the session
        return await self.issue_tokens(user, institution, session, mfa_enabled=mfa_enabled)

    async def issue_tokens(
        self, user: User, institution: Institution | None, session: UserSession, *, mfa_enabled: bool
    ) -> IssuedTokens:
        """Create a new one-time refresh token plus an access token bound to ``session``; the access token carries the
        person's effective permissions (role defaults, scopes, their own grants and removals)."""
        now = utcnow()
        permissions = await PermissionService(self.db).effective_for(user)
        admin_orgs: list[int] = []
        if user.role == Role.ADMIN:
            admin_orgs = list(
                (
                    await self.db.execute(
                        select(Institution.public_id).where(Institution.admin_id == user.id, Institution.deleted_at.is_(None))
                    )
                ).scalars()
            )
        raw_refresh_token = generate_secure_token()
        refresh_expires_at = min(now + timedelta(days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS), session.expires_at)
        self.repo.add(
            RefreshToken(
                id=uuid7(),
                session_id=session.id,
                token_hash=hash_token(raw_refresh_token),
                expires_at=refresh_expires_at,
            )
        )
        access_token, expires_in = create_access_token(
            user_id=user.public_id,
            session_id=session.public_id,
            role=user.role,
            organization_id=institution.public_id if institution else None,
            token_version=user.token_version,
            organization_type=institution.org_type if institution else None,
            scopes=permissions,
            admin_organization_ids=admin_orgs,
        )
        return IssuedTokens(
            token=TokenOut(
                access_token=access_token,
                refresh_token=raw_refresh_token,
                expires_in=expires_in,
                refresh_expires_in=max(int((refresh_expires_at - now).total_seconds()), 0),
            ),
            user=AuthUserOut(
                user_id=user.public_id,
                full_name=user.full_name,
                email=user.email,
                username=user.username,
                role=user.role,
                institution=InstitutionRef.of(institution),
                scopes=permissions,
                must_change_password=user.must_change_password,
                mfa_enabled=mfa_enabled,
                mfa_setup_required=not mfa_enabled and user.role in self.settings.MFA_REQUIRED_ROLES,
            ),
        )

    async def revoke_session(self, session_id: uuid.UUID, *, reason: str) -> None:
        session = await self.repo.get_session(session_id)
        if session is not None:
            self.repo.revoke(session, reason=reason, now=utcnow())

    async def revoke_all_for_user(self, user: User, *, reason: str) -> int:
        """End every session and invalidate every outstanding access token of ``user``."""
        user.token_version += 1
        return await self.repo.revoke_all_for_user(user, reason=reason, now=utcnow())

    async def revoke_all_for_institution(self, institution_id: uuid.UUID, *, reason: str) -> int:
        await self.users.bump_token_version_for_institution(institution_id)
        return await self.repo.revoke_all_for_institution(institution_id, reason=reason, now=utcnow())
