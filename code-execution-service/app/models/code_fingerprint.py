import uuid

from sqlalchemy import BigInteger, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CodeFingerprint(Base):
    """One winnowing hash of a submission's token stream (see app/utils/fingerprint.py). Looking up
    every submission that shares hashes with a new one, within the same problem, finds copies without
    comparing the new code against every old submission."""

    __tablename__ = "code_fingerprints"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), primary_key=True
    )
    hash: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    problem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))

    __table_args__ = (Index("ix_code_fingerprints_problem_hash", "problem_id", "hash"),)
