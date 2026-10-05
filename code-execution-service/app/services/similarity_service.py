from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.enums import LanguageKind
from app.models.code_fingerprint import CodeFingerprint
from app.models.submission import Submission
from app.utils.fingerprint import fingerprint, similarity_percent

_CANDIDATES = 50  # most-overlapping earlier submissions considered per submission


class SimilarityService:
    """Plagiarism signal (docs/PRODUCT.md §5.2): fingerprint each submission and find earlier submissions to the
    same problem by other people that share most of it. It flags for a human reviewer; it never decides."""

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def index_and_compare(self, submission: Submission, kind: LanguageKind) -> None:
        """Store this submission's fingerprint and record its closest match. Safe to repeat (a re-judge)."""
        hashes = fingerprint(
            submission.source,
            kind,
            min_tokens=self.settings.SIMILARITY_MIN_TOKENS,
            max_hashes=self.settings.FINGERPRINT_MAX_HASHES,
        )
        await self.db.execute(delete(CodeFingerprint).where(CodeFingerprint.submission_id == submission.id))
        submission.fingerprint_count = len(hashes)
        submission.flagged = False
        submission.similarity_percent = None
        submission.similar_to_public_id = None
        if not hashes:  # too short to say anything about
            return
        await self.db.execute(
            insert(CodeFingerprint),
            [{"submission_id": submission.id, "hash": value, "problem_id": submission.problem_id} for value in hashes],
        )
        await self.db.flush()

        matches = await self._matches(submission, hashes)
        if matches:
            best, percent = matches[0]
            submission.similarity_percent = percent
            submission.similar_to_public_id = best.public_id
            submission.flagged = percent >= self.settings.SIMILARITY_FLAG_PERCENT

    async def similar_to(self, submission: Submission) -> list[tuple[Submission, int]]:
        """The closest other submissions to ``submission``, for a reviewer looking at a flag."""
        hashes = set(
            (
                await self.db.execute(select(CodeFingerprint.hash).where(CodeFingerprint.submission_id == submission.id))
            ).scalars()
        )
        if not hashes:
            return []
        floor = self.settings.SIMILARITY_LIST_MIN_PERCENT  # every program shares small fragments with every other
        return [(other, percent) for other, percent in await self._matches(submission, hashes) if percent >= floor]

    async def _matches(self, submission: Submission, hashes: set[int]) -> list[tuple[Submission, int]]:
        shared = (
            await self.db.execute(
                select(CodeFingerprint.submission_id, func.count().label("shared"))
                .where(
                    CodeFingerprint.problem_id == submission.problem_id,
                    CodeFingerprint.hash.in_(hashes),
                    CodeFingerprint.submission_id != submission.id,
                )
                .group_by(CodeFingerprint.submission_id)
                .order_by(func.count().desc())
                .limit(_CANDIDATES)
            )
        ).all()
        if not shared:
            return []
        counts = {submission_id: count for submission_id, count in shared}
        others = (
            await self.db.execute(
                select(Submission).where(Submission.id.in_(counts), Submission.user_id != submission.user_id)
            )
        ).scalars()  # one's own earlier attempts are not copying
        scored = [
            (other, similarity_percent(counts[other.id], len(hashes), other.fingerprint_count or counts[other.id]))
            for other in others
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored
