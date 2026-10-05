import asyncio
import time

from lms_common.pagination import paginate
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.ids import new_public_id
from app.domain.enums import IdempotentScope, JobStatus, Priority, ProblemStatus
from app.models.language import Language
from app.models.problem import Problem
from app.models.submission import Submission
from app.schemas.common import ReviewSubmissionQuery, SubmissionQuery
from app.services.idempotency_service import IdempotencyService, request_hash
from app.services.language_service import LanguageService
from app.services.problem_service import allowed_language_codes
from app.services.rate_limiter import RateLimiter
from app.services.rate_limits import enforce_submission_limits
from app.services.run_service import check_source_sizes


class SubmissionService:
    def __init__(self, db: AsyncSession, settings: Settings, limiter: RateLimiter | None = None) -> None:
        self.db = db
        self.settings = settings
        self.limiter = limiter

    async def create(
        self,
        *,
        user_id: int,
        organization_id: int | None,
        problem: Problem,
        language_code: str,
        source: str,
        priority: Priority,
        reference: str | None = None,
        key: str | None = None,
    ) -> Submission:
        """Queue a solution for judging. ``limiter`` set means a person is submitting (rate limited); the
        internal exam path passes none, since assessment-service paces its own students."""
        if problem.status != ProblemStatus.PUBLISHED:
            raise NotFoundError("Problem not found.", code="PROBLEM_NOT_FOUND")
        language = await self._allowed_language(problem, language_code)
        check_source_sizes(self.settings, source)

        idempotency = IdempotencyService(self.db)
        payload_hash = request_hash(
            {"problem": problem.public_id, "language": language.code, "source": source, "reference": reference, "priority": int(priority)}
        )
        if key:
            existing = await idempotency.find(user_id, IdempotentScope.SUBMISSION, key, payload_hash)
            if existing is not None:
                return await self.get(existing)
        if self.limiter is not None:
            await enforce_submission_limits(self.limiter, self.settings, user_id, organization_id)

        submission = Submission(
            public_id=new_public_id(),
            user_id=user_id,
            organization_id=organization_id,
            problem_id=problem.id,
            problem_public_id=problem.public_id,
            language_code=language.code,
            source=source,
            reference=reference,
            priority=priority,
        )
        self.db.add(submission)
        if key:
            idempotency.remember(user_id, IdempotentScope.SUBMISSION, key, payload_hash, submission.public_id)
        try:
            await self.db.commit()
        except IntegrityError:  # two requests with one key raced; the other one won
            await self.db.rollback()
            existing = await idempotency.find(user_id, IdempotentScope.SUBMISSION, key or "", payload_hash)
            if existing is None:
                raise
            return await self.get(existing)
        return await self.get(submission.public_id)

    async def get(self, public_id: int) -> Submission:
        submission = (
            await self.db.execute(
                select(Submission)
                .where(Submission.public_id == public_id)
                .options(selectinload(Submission.results))
                .execution_options(populate_existing=True)  # always what is in the database now, results included
            )
        ).scalar_one_or_none()
        if submission is None:
            raise NotFoundError("Submission not found.", code="SUBMISSION_NOT_FOUND")
        return submission

    async def wait_until_done(self, submission: Submission, wait_seconds: float) -> Submission:
        """Long-poll: return once judging completes, or after ``wait_seconds`` whatever its state."""
        deadline = time.monotonic() + min(wait_seconds, self.settings.RESULT_WAIT_MAX_SECONDS)
        status = submission.status
        while status != JobStatus.COMPLETED and time.monotonic() < deadline:
            await asyncio.sleep(self.settings.RESULT_POLL_INTERVAL_SECONDS)
            status = (await self.db.execute(select(Submission.status).where(Submission.id == submission.id))).scalar_one()
            await self.db.commit()  # end the read transaction so the next poll sees newer commits
        self.db.expunge(submission)  # its results were loaded empty while queued; reload it from scratch
        return await self.get(submission.public_id)

    async def get_visible(self, public_id: int, *, user_id: int, is_reviewer: bool) -> Submission:
        """Your own submission, or any if you review. Someone else's looks like a missing one."""
        submission = await self.get(public_id)
        if submission.user_id != user_id and not is_reviewer:
            raise NotFoundError("Submission not found.", code="SUBMISSION_NOT_FOUND")
        return submission

    async def list_submissions(
        self, query: SubmissionQuery | ReviewSubmissionQuery, *, user_id: int | None
    ) -> tuple[list[Submission], int, bool]:
        """``user_id`` set: that user's own submissions. None: reviewers' view of everyone's."""
        stmt = select(Submission)
        if user_id is not None:
            stmt = stmt.where(Submission.user_id == user_id)
        if query.problem_id:
            stmt = stmt.where(Submission.problem_public_id == query.problem_id)
        if query.status:
            stmt = stmt.where(Submission.status == query.status)
        if query.verdict:
            stmt = stmt.where(Submission.verdict == query.verdict)
        if isinstance(query, ReviewSubmissionQuery):
            if query.user_id:
                stmt = stmt.where(Submission.user_id == query.user_id)
            if query.reference:
                stmt = stmt.where(Submission.reference == query.reference)
            if query.flagged is not None:
                stmt = stmt.where(Submission.flagged.is_(query.flagged))
        stmt = stmt.order_by(
            Submission.created_at.desc() if query.sort_order == "desc" else Submission.created_at.asc(), Submission.id
        )
        return await paginate(self.db, stmt, query.page, query.per_page)

    async def _allowed_language(self, problem: Problem, language_code: str) -> Language:
        enabled = await LanguageService(self.db).list_languages()
        allowed = allowed_language_codes(problem, enabled)
        language = next((candidate for candidate in enabled if candidate.code == language_code), None)
        if language is None or language.code not in allowed:
            raise ValidationFailedError(
                details=[
                    {
                        "field": "language",
                        "code": "LANGUAGE_NOT_ALLOWED",
                        "message": f"Use one of: {', '.join(sorted(allowed))}" if allowed else "No language is available for this problem",
                    }
                ]
            )
        return language
