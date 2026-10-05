import asyncio
import time

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import BadRequestError, NotFoundError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.domain.enums import IdempotentScope, JobStatus, LanguageKind, Priority, ProblemStatus, ProblemType
from app.models.problem import Problem
from app.models.run import Run
from app.permissions.policy import can_review
from app.schemas.run import RunCreate
from app.services.idempotency_service import IdempotencyService, request_hash
from app.services.language_service import LanguageService
from app.services.rate_limiter import RateLimiter
from app.services.rate_limits import enforce_run_limits


def check_source_sizes(settings: Settings, source: str, stdin: str = "", *, allow_empty: bool = False) -> None:
    details = []
    if len(source.encode()) > settings.MAX_SOURCE_BYTES:
        details.append({"field": "source", "code": "SOURCE_TOO_LARGE", "message": f"At most {settings.MAX_SOURCE_BYTES} bytes"})
    if not source.strip() and not allow_empty:
        details.append({"field": "source", "code": "REQUIRED", "message": "Write some code first"})
    if len(stdin.encode()) > settings.MAX_STDIN_BYTES:
        details.append({"field": "stdin", "code": "STDIN_TOO_LARGE", "message": f"At most {settings.MAX_STDIN_BYTES} bytes"})
    if details:
        raise ValidationFailedError(details=details)


class RunService:
    """Runs of code on custom input: create (queue) and read back. The worker does the executing."""

    def __init__(self, db: AsyncSession, settings: Settings, limiter: RateLimiter | None = None) -> None:
        self.db = db
        self.settings = settings
        self.limiter = limiter

    async def create(self, auth: AccessTokenClaims, data: RunCreate, key: str | None) -> Run:
        language = await LanguageService(self.db).get(data.language)
        check_source_sizes(self.settings, data.source, data.stdin)
        await self._check_problem_context(auth, data, language.kind)

        idempotency = IdempotencyService(self.db)
        payload_hash = request_hash(data.model_dump(mode="json"))
        if key:
            existing = await idempotency.find(auth.user_id, IdempotentScope.RUN, key, payload_hash)
            if existing is not None:
                return await self._get(existing)
        if self.limiter is None:
            raise RuntimeError("a run started by a person needs the rate limiter")
        await enforce_run_limits(self.limiter, self.settings, auth.user_id, auth.organization_id)

        run = Run(
            public_id=new_public_id(),
            user_id=auth.user_id,
            organization_id=auth.organization_id,
            language_code=language.code,
            problem_public_id=data.problem_id,
            source=data.source,
            stdin=data.stdin,
            priority=Priority.PRACTICE,
        )
        self.db.add(run)
        if key:
            idempotency.remember(auth.user_id, IdempotentScope.RUN, key, payload_hash, run.public_id)
        try:
            await self.db.commit()
        except IntegrityError:  # two requests with one key raced; the other one won
            await self.db.rollback()
            existing = await idempotency.find(auth.user_id, IdempotentScope.RUN, key or "", payload_hash)
            if existing is None:
                raise
            return await self._get(existing)
        return run

    async def create_for_service(self, *, user_id: int, organization_id: int | None, language: str, source: str, stdin: str) -> Run:
        """A run another service starts on a person's behalf (the interviewer's coding round). The caller paces its own users, so no per-user
        limiter applies; the source and input size limits still do."""
        lang = await LanguageService(self.db).get(language)
        check_source_sizes(self.settings, source, stdin)
        run = Run(
            public_id=new_public_id(), user_id=user_id, organization_id=organization_id, language_code=lang.code, problem_public_id=None, source=source, stdin=stdin,
            priority=Priority.PRACTICE,
        )
        self.db.add(run)
        await self.db.commit()
        return run

    async def get_for_user(self, public_id: int, user_id: int) -> Run:
        """Only the person who ran the code can read the run: another user's run looks like a missing one."""
        run = await self._get(public_id)
        if run.user_id != user_id:
            raise NotFoundError("Run not found.", code="RUN_NOT_FOUND")
        return run

    async def wait_until_done(self, run: Run, wait_seconds: float) -> Run:
        """Long-poll: return as soon as the run completes, or after ``wait_seconds`` whatever its state."""
        deadline = time.monotonic() + min(wait_seconds, self.settings.RESULT_WAIT_MAX_SECONDS)
        while run.status != JobStatus.COMPLETED and time.monotonic() < deadline:
            await asyncio.sleep(self.settings.RESULT_POLL_INTERVAL_SECONDS)
            await self.db.refresh(run)
            await self.db.commit()  # end the read transaction so the next poll sees newer commits
        return run

    async def get(self, public_id: int) -> Run:
        return await self._get(public_id)

    async def _get(self, public_id: int) -> Run:
        run = (await self.db.execute(select(Run).where(Run.public_id == public_id))).scalar_one_or_none()
        if run is None:
            raise NotFoundError("Run not found.", code="RUN_NOT_FOUND")
        return run

    async def _check_problem_context(self, auth: AccessTokenClaims, data: RunCreate, kind: str) -> None:
        if data.problem_id is None:
            return
        if kind != LanguageKind.SQL:
            raise BadRequestError("problem_id is only used for SQL runs.", code="RUN_PROBLEM_NOT_SQL")
        problem = (await self.db.execute(select(Problem).where(Problem.public_id == data.problem_id))).scalar_one_or_none()
        if problem is None or (problem.status != ProblemStatus.PUBLISHED and not can_review(auth)):
            raise NotFoundError("Problem not found.", code="PROBLEM_NOT_FOUND")
        if problem.problem_type != ProblemType.SQL:
            raise BadRequestError("This problem is not a SQL problem.", code="RUN_PROBLEM_NOT_SQL")
