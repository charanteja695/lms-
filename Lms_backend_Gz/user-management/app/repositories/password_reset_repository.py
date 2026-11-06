import uuid
from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.password_reset import PasswordResetPurpose, PasswordResetRequest


class PasswordResetRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def add(self, request: PasswordResetRequest) -> None:
        self.db.add(request)

    async def get_open_otp_request(self, user_id: uuid.UUID, *, now: datetime) -> PasswordResetRequest | None:
        stmt = (
            select(PasswordResetRequest)
            .where(
                PasswordResetRequest.user_id == user_id,
                PasswordResetRequest.purpose == PasswordResetPurpose.PASSWORD_RESET,
                PasswordResetRequest.otp_hash.is_not(None),
                PasswordResetRequest.consumed_at.is_(None),
                PasswordResetRequest.verified_at.is_(None),
                PasswordResetRequest.expires_at > now,
            )
            .order_by(PasswordResetRequest.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_token_hash(self, token_hash: str) -> PasswordResetRequest | None:
        stmt = (
            select(PasswordResetRequest)
            .where(
                or_(
                    PasswordResetRequest.link_token_hash == token_hash,
                    PasswordResetRequest.reset_token_hash == token_hash,
                )
            )
            .with_for_update()
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def consume_all_open(self, user_id: uuid.UUID, *, now: datetime) -> None:
        await self.db.execute(
            update(PasswordResetRequest)
            .where(PasswordResetRequest.user_id == user_id, PasswordResetRequest.consumed_at.is_(None))
            .values(consumed_at=now)
            .execution_options(synchronize_session="fetch")
        )
