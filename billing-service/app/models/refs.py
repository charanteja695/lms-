"""Read-models built from other services' events."""

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class OrgRef(TimestampMixin, Base):
    __tablename__ = "org_refs"

    org_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(200), default="")
    org_type: Mapped[str] = mapped_column(String(12), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
