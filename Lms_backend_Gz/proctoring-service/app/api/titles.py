"""Test names for lists, so nobody has to read a test id."""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import TestRef


async def test_titles(db: AsyncSession, test_ids: Iterable[int]) -> dict[int, str]:
    ids = set(test_ids)
    if not ids:
        return {}
    return dict((await db.execute(select(TestRef.test_id, TestRef.title).where(TestRef.test_id.in_(ids)))).tuples().all())
