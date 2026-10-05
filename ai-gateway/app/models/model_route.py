"""Which provider(s) serve a capability, in fallback order (docs/PRODUCT.md §6: "provider routing").

One row per capability. ``providers`` is an ordered list of ``{"provider": "anthropic", "model": "claude-sonnet-5"}``;
the router (app/providers/router.py) tries them in order, falling back to the next on a transient failure. Seeded by
the initial migration from the same defaults ``Settings`` would otherwise fall back to, so ``GET /models`` always has
something to show; an admin can reorder or add providers with ``PATCH /models/{capability}``.
"""

from typing import Any

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.types import JSONType


class ModelRoute(TimestampMixin, Base):
    __tablename__ = "model_routes"

    capability: Mapped[str] = mapped_column(String(20), primary_key=True)
    providers: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    updated_by: Mapped[int | None] = mapped_column(BigInteger)
