import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_state import ORGANIZATION_REVOKED, SESSION_REVOKED, USER_REVOKED
from app.db.types import uuid7
from app.models.institution import Institution
from app.models.outbox_event import OutboxEvent
from app.models.session import RefreshToken, UserSession
from app.models.user import User


class SessionRepository:
    """Every sign-out goes through this class, so each one also records an ``access.*`` event that
    tells other services to stop accepting the affected access tokens (see app/core/access_state.py)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_session(self, session_id: uuid.UUID) -> UserSession | None:
        return await self.db.get(UserSession, session_id)

    async def get_session_by_public_id(self, public_id: int) -> UserSession | None:
        stmt = select(UserSession).where(UserSession.public_id == public_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_active_for_user(self, user_id: uuid.UUID, *, now: datetime) -> list[UserSession]:
        stmt = (
            select(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None), UserSession.expires_at > now)
            .order_by(UserSession.last_used_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_refresh_token(self, token_hash: str, *, for_update: bool = False) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        if for_update:
            stmt = stmt.with_for_update()
        return (await self.db.execute(stmt)).scalar_one_or_none()

    def add(self, obj: UserSession | RefreshToken) -> None:
        self.db.add(obj)

    def revoke(self, session: UserSession, *, reason: str, now: datetime) -> None:
        if session.revoked_at is None:
            session.revoked_at = now
            session.revoked_reason = reason
            self._access_event(
                SESSION_REVOKED, "session", session.id, {"session_id": str(session.public_id), "reason": reason}
            )

    async def revoke_all_for_user(self, user: User, *, reason: str, now: datetime) -> int:
        """Callers bump ``user.token_version`` first; tokens with an older version stop working everywhere."""
        result = await self.db.execute(
            update(UserSession)
            .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
            .values(revoked_at=now, revoked_reason=reason)
            .execution_options(synchronize_session="fetch")
        )
        self._access_event(
            USER_REVOKED,
            "user",
            user.id,
            {"user_id": str(user.public_id), "token_version": user.token_version, "reason": reason},
        )
        return result.rowcount or 0  # type: ignore[attr-defined]

    async def revoke_all_for_institution(self, institution_id: uuid.UUID, *, reason: str, now: datetime) -> int:
        member_ids = select(User.id).where(User.institution_id == institution_id)
        result = await self.db.execute(
            update(UserSession)
            .where(UserSession.user_id.in_(member_ids), UserSession.revoked_at.is_(None))
            .values(revoked_at=now, revoked_reason=reason)
            .execution_options(synchronize_session="fetch")
        )
        public_id = (
            await self.db.execute(select(Institution.public_id).where(Institution.id == institution_id))
        ).scalar_one()
        self._access_event(
            ORGANIZATION_REVOKED,
            "institution",
            institution_id,
            {"organization_id": str(public_id), "revoked_at": int(now.timestamp()), "reason": reason},
        )
        return result.rowcount or 0  # type: ignore[attr-defined]

    def _access_event(
        self, event_type: str, aggregate_type: str, aggregate_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        self.db.add(
            OutboxEvent(
                id=uuid7(),
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload=payload,
            )
        )
