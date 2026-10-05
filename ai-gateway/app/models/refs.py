"""Read-model from user-management's events (a service never reads another's tables). The one fact this
service needs about an org that it did not itself decide: whether it is suspended, so a suspended
institution's staff or tutor cannot keep spending its AI quota after seats are pulled."""

from sqlalchemy import BigInteger, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class OrgStatusRef(TimestampMixin, Base):
    __tablename__ = "org_status_refs"

    organization_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    suspended: Mapped[bool] = mapped_column(Boolean, default=False)
