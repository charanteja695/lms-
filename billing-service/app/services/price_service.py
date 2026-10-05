"""The price list: per-seat course prices and employer plan tiers, kept by a billing admin."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.ids import new_public_id
from app.domain.enums import PriceKind
from app.models.billing import PriceItem


class PriceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, public_id: int) -> PriceItem:
        item = (await self.db.execute(select(PriceItem).where(PriceItem.public_id == public_id))).scalar_one_or_none()
        if item is None:
            raise NotFoundError("Price not found.", code="PRICE_NOT_FOUND")
        return item

    async def by_code(self, kind: PriceKind, code: str) -> PriceItem | None:
        return (await self.db.execute(select(PriceItem).where(PriceItem.kind == kind, PriceItem.code == code, PriceItem.active.is_(True)))).scalar_one_or_none()

    async def list_prices(self, *, kind: str | None, include_inactive: bool, page: int, per_page: int) -> tuple[list[PriceItem], int]:
        stmt = select(PriceItem)
        if kind:
            stmt = stmt.where(PriceItem.kind == kind)
        if not include_inactive:
            stmt = stmt.where(PriceItem.active.is_(True))
        total = int((await self.db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one())
        rows: Any = (await self.db.execute(stmt.order_by(PriceItem.kind, PriceItem.code).limit(per_page).offset((page - 1) * per_page))).scalars()
        return list(rows), total

    async def create(self, fields: dict[str, Any]) -> PriceItem:
        if (await self.db.execute(select(PriceItem.id).where(PriceItem.kind == fields["kind"], PriceItem.code == fields["code"]))).first() is not None:
            raise ConflictError("There is already a price for this.", code="PRICE_EXISTS")
        item = PriceItem(public_id=new_public_id(), **fields)
        self.db.add(item)
        await self.db.commit()
        return item

    async def update(self, item: PriceItem, fields: dict[str, Any]) -> PriceItem:
        """A price change never touches an invoice or quote already made: those froze the amount they used."""
        for name, value in fields.items():
            setattr(item, name, value)
        await self.db.commit()
        return item
