"""Offset pagination that stays fast and safe at millions of rows (see lms-backend/README.md).

Counting every match is slow on huge tables, so counts stop at ``MAX_COUNTED_RECORDS`` and the
caller's list endpoint should refuse to page past that window too (larger result sets belong in
an export). This mirrors user-management's ``app/utils/query.py``, generalised to any SQLAlchemy
``Select``.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.interfaces import ORMOption

LIKE_ESCAPE = "\\"
MAX_COUNTED_RECORDS = 10_000


def contains_pattern(value: str) -> str:
    """Build a safe ``%value%`` LIKE pattern, escaping wildcard characters from user input."""
    escaped = value.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2).replace("%", r"\%").replace("_", r"\_")
    return f"%{escaped}%"


async def paginate(
    db: AsyncSession,
    stmt: Select[Any],
    page: int,
    per_page: int,
    *,
    options: Sequence[ORMOption] = (),
) -> tuple[list[Any], int, bool]:
    """Return ``(items, total, total_is_exact)``; ``total`` is capped at MAX_COUNTED_RECORDS."""
    capped = stmt.order_by(None).limit(MAX_COUNTED_RECORDS + 1).subquery()
    total = int((await db.execute(select(func.count()).select_from(capped))).scalar_one())
    page_stmt = stmt.options(*options).limit(per_page).offset((page - 1) * per_page)
    rows = await db.execute(page_stmt)
    is_exact = total <= MAX_COUNTED_RECORDS
    return list(rows.unique().scalars().all()), min(total, MAX_COUNTED_RECORDS), is_exact
