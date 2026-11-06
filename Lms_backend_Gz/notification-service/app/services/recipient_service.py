from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import UserStatus
from app.services.notification_service import Recipient
from app.services.user_ref_service import UserRefService


class RecipientService:
    """Resolves who should get a notification from the local recipient directory.

    A user missing from the directory (they were created before this service started listening)
    still gets the in-app notification, keyed by their id; only email needs the directory.
    Suspended and deleted users get nothing."""

    def __init__(self, db: AsyncSession) -> None:
        self.users = UserRefService(db)

    async def for_user(self, user_id: int) -> list[Recipient]:
        ref = await self.users.get(user_id)
        if ref is None:
            return [Recipient(user_id=user_id, organization_id=None, first_name="", email=None)]
        if ref.status != UserStatus.ACTIVE:
            return []
        return [Recipient(user_id=ref.user_id, organization_id=ref.organization_id, first_name=ref.first_name, email=ref.email)]

    async def institution_heads(self, organization_id: int) -> list[Recipient]:
        return [
            Recipient(user_id=ref.user_id, organization_id=ref.organization_id, first_name=ref.first_name, email=ref.email)
            for ref in await self.users.institution_heads(organization_id)
        ]
