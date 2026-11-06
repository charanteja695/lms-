"""Turns a claimed job into a result: executes a run, or judges a submission against every test case.

Failure handling has two very different cases and this module keeps them apart:
- the *program* failed (wrong answer, crash, too slow): that is the verdict, recorded and final;
- the *engine* failed (Judge0 unreachable, engine internal error): not the student's fault, so the job goes
  back on the queue with a backoff, and only after JOB_MAX_ATTEMPTS is it given up as ``internal_error``.
"""

import asyncio
import uuid
from dataclasses import dataclass, replace
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.crypto import SecretCipher
from app.core.time import utcnow
from app.domain.enums import CompareMode, JobStatus, LanguageKind, Verdict
from app.engines.base import EngineError, ExecutionEngine, ExecutionRequest, ExecutionResult, Outcome
from app.models.problem import Problem
from app.models.run import Run
from app.models.submission import Submission
from app.models.submission_result import SubmissionResult
from app.models.test_case import TestCase
from app.services.language_service import LanguageService
from app.services.limits import problem_limits, run_limits
from app.services.outbox import write_event
from app.services.similarity_service import SimilarityService
from app.utils.comparison import compare_output

_VERDICT_OF_OUTCOME = {
    Outcome.COMPILATION_ERROR: Verdict.COMPILATION_ERROR,
    Outcome.RUNTIME_ERROR: Verdict.RUNTIME_ERROR,
    Outcome.TIME_LIMIT_EXCEEDED: Verdict.TIME_LIMIT_EXCEEDED,
    Outcome.MEMORY_LIMIT_EXCEEDED: Verdict.MEMORY_LIMIT_EXCEEDED,
    Outcome.OUTPUT_LIMIT_EXCEEDED: Verdict.OUTPUT_LIMIT_EXCEEDED,
}
_MAX_BACKOFF_SECONDS = 30
_MESSAGE_LIMIT = 300
_SAMPLE_OUTPUT_LIMIT = 4_000


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


@dataclass(frozen=True, slots=True)
class CaseOutcome:
    case: TestCase
    test_input: str
    expected: str
    verdict: Verdict
    result: ExecutionResult


class JudgeService:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        engine: ExecutionEngine,
        settings: Settings,
        cipher: SecretCipher,
    ) -> None:
        self.sessionmaker = sessionmaker
        self.engine = engine
        self.settings = settings
        self.cipher = cipher

    # ------------------------------------------------------------------ runs

    async def process_run(self, run_id: uuid.UUID) -> None:
        # Three steps, and the database connection is held only for the first and the last: code can run for
        # seconds, and one open connection per execution in flight would exhaust the pool (and any pooler).
        async with self.sessionmaker() as db:  # 1. read what is needed
            run = await db.get(Run, run_id)
            if run is None or run.status == JobStatus.COMPLETED:
                return
            if run.attempts > self.settings.JOB_MAX_ATTEMPTS:  # claimed again and again: the worker keeps dying on it
                self._finish_run(run, ExecutionResult(Outcome.INTERNAL_ERROR, message="The run could not be completed"))
                await db.commit()
                return
            language = await LanguageService(db).get(run.language_code, must_be_enabled=False)
            request = ExecutionRequest(
                LanguageService.to_spec(language),
                run.source,
                run.stdin,
                run_limits(self.settings, language),
                await self._problem_setup(db, run.problem_public_id),
            )

        result: ExecutionResult | None = None  # 2. run it, holding no connection
        failure = ""
        try:
            result = await self.engine.execute(request)
            if result.outcome == Outcome.INTERNAL_ERROR:
                failure, result = result.message or "engine internal error", None
        except EngineError as exc:
            failure = str(exc)

        async with self.sessionmaker() as db:  # 3. record the outcome
            run = await db.get(Run, run_id)
            if run is None or run.status == JobStatus.COMPLETED:
                return  # a lapsed lease handed it to another worker that finished first; keep theirs
            if result is None:
                self._retry_or_give_up(run, failure)
            else:
                self._finish_run(run, result)
            await db.commit()

    def _finish_run(self, run: Run, result: ExecutionResult) -> None:
        limit = self.settings.MAX_OUTPUT_BYTES
        run.status = JobStatus.COMPLETED
        run.outcome = result.outcome
        run.stdout = _clip(result.stdout, limit)
        run.stderr = _clip(result.stderr, limit)
        run.compile_output = _clip(result.compile_output, limit)
        run.message = _clip(result.message, 500) or None
        run.time_ms = result.time_ms
        run.memory_kb = result.memory_kb
        run.exit_code = result.exit_code
        run.finished_at = utcnow()

    async def _problem_setup(self, db: AsyncSession, problem_public_id: int | None) -> str:
        if problem_public_id is None:
            return ""
        encrypted = (
            await db.execute(select(Problem.setup_sql_encrypted).where(Problem.public_id == problem_public_id))
        ).scalar_one_or_none()
        return self.cipher.decrypt(encrypted) if encrypted else ""

    # ------------------------------------------------------------------ submissions

    async def process_submission(self, submission_id: uuid.UUID) -> None:
        # Read, then run every test case holding no connection, then record (see process_run).
        async with self.sessionmaker() as db:
            submission = await db.get(Submission, submission_id)
            if submission is None or submission.status == JobStatus.COMPLETED:
                return
            if submission.attempts > self.settings.JOB_MAX_ATTEMPTS:
                await self._finish_without_cases(db, submission, "The submission could not be judged")
                return
            problem = (
                await db.execute(
                    select(Problem).where(Problem.id == submission.problem_id).options(selectinload(Problem.test_cases))
                )
            ).scalar_one()
            if not problem.test_cases:
                await self._finish_without_cases(db, submission, "The problem has no test cases")
                return
            language = await LanguageService(db).get(submission.language_code, must_be_enabled=False)
            kind = LanguageKind(language.kind)
            base = ExecutionRequest(
                LanguageService.to_spec(language),
                submission.source,
                "",
                problem_limits(self.settings, problem, language),
                self.cipher.decrypt(problem.setup_sql_encrypted) if problem.setup_sql_encrypted else "",
            )
            cases = list(problem.test_cases)

        outcomes: list[CaseOutcome] | None = None
        failure = ""
        try:
            outcomes = await self._run_cases(base, problem, cases)
        except EngineError as exc:
            failure = str(exc)

        async with self.sessionmaker() as db:
            submission = await db.get(Submission, submission_id)
            if submission is None or submission.status == JobStatus.COMPLETED:
                return  # a lapsed lease handed it to another worker that finished first; keep theirs
            if outcomes is None:
                self._retry_or_give_up(submission, failure)
                if submission.status == JobStatus.COMPLETED:
                    self._emit_judged(db, submission)
                await db.commit()
                return
            await self._record(db, submission, kind, outcomes)

    async def _run_cases(self, base: ExecutionRequest, problem: Problem, cases: list[TestCase]) -> list[CaseOutcome]:
        """Run the first case alone: a compile error would repeat identically on every case, so it is
        reported once instead of compiling N times. The rest run with bounded concurrency."""
        first = await self._run_case(base, problem, cases[0])
        if first.result.outcome == Outcome.COMPILATION_ERROR:
            failed = [first]
            for case in cases[1:]:  # each case keeps its own input and expected output
                test_input, expected = self.cipher.decrypt(case.input_encrypted), self.cipher.decrypt(case.expected_encrypted)
                failed.append(CaseOutcome(case, test_input, expected, Verdict.COMPILATION_ERROR, first.result))
            return failed

        semaphore = asyncio.Semaphore(self.settings.JUDGE_CASE_CONCURRENCY)

        async def limited(case: TestCase) -> CaseOutcome:
            async with semaphore:
                return await self._run_case(base, problem, case)

        rest = await asyncio.gather(*(limited(case) for case in cases[1:]), return_exceptions=True)
        for item in rest:
            if isinstance(item, BaseException):
                raise item  # an engine failure (or a bug) anywhere aborts the whole judging: no partial verdicts
        return [first, *[item for item in rest if isinstance(item, CaseOutcome)]]

    async def _run_case(self, base: ExecutionRequest, problem: Problem, case: TestCase) -> CaseOutcome:
        test_input = self.cipher.decrypt(case.input_encrypted)
        expected = self.cipher.decrypt(case.expected_encrypted)
        if base.language.kind == LanguageKind.SQL:  # the case's "input" is seed data for this dataset, run after the schema
            request = replace(base, stdin="", setup=(base.setup + chr(10) + test_input) if test_input else base.setup)
        else:
            request = replace(base, stdin=test_input)
        result = await self.engine.execute(request)
        if result.outcome == Outcome.INTERNAL_ERROR:
            raise EngineError(result.message or "engine internal error")
        if result.outcome == Outcome.OK:
            mode = CompareMode(case.compare_mode or problem.compare_mode)
            same = compare_output(mode, expected, result.stdout, tolerance=problem.float_tolerance)
            verdict = Verdict.ACCEPTED if same else Verdict.WRONG_ANSWER
        else:
            verdict = _VERDICT_OF_OUTCOME[result.outcome]
        return CaseOutcome(case, test_input, expected, verdict, result)

    async def _record(self, db: AsyncSession, submission: Submission, kind: LanguageKind, outcomes: list[CaseOutcome]) -> None:
        await db.execute(delete(SubmissionResult).where(SubmissionResult.submission_id == submission.id))
        rows: list[SubmissionResult] = []
        for outcome in outcomes:
            case = outcome.case
            sample = case.is_sample
            message = None
            if sample:  # hidden cases keep the verdict alone: an error message could quote the hidden input
                message = _clip(outcome.result.message or outcome.result.stderr, _MESSAGE_LIMIT) or None
            rows.append(
                SubmissionResult(
                    submission_id=submission.id,
                    test_case_public_id=case.public_id,
                    position=case.position,
                    is_sample=sample,
                    weight=case.weight,
                    verdict=outcome.verdict,
                    time_ms=outcome.result.time_ms,
                    memory_kb=outcome.result.memory_kb,
                    message=message,
                    sample_input=outcome.test_input if sample else None,
                    sample_expected=outcome.expected if sample else None,
                    sample_actual=_clip(outcome.result.stdout, _SAMPLE_OUTPUT_LIMIT) if sample else None,
                )
            )
        db.add_all(rows)

        accepted = [outcome for outcome in outcomes if outcome.verdict == Verdict.ACCEPTED]
        total_weight = sum(outcome.case.weight for outcome in outcomes)
        submission.verdict = next((o.verdict for o in outcomes if o.verdict != Verdict.ACCEPTED), Verdict.ACCEPTED)
        submission.passed_count = len(accepted)
        submission.total_count = len(outcomes)
        submission.score = round(100 * sum(o.case.weight for o in accepted) / total_weight) if total_weight else 0
        times = [o.result.time_ms for o in outcomes if o.result.time_ms is not None]
        memories = [o.result.memory_kb for o in outcomes if o.result.memory_kb is not None]
        submission.time_ms = max(times) if times else None
        submission.memory_kb = max(memories) if memories else None
        submission.compile_output = None
        if submission.verdict == Verdict.COMPILATION_ERROR:
            first = outcomes[0].result
            submission.compile_output = _clip(first.compile_output or first.message, self.settings.MAX_OUTPUT_BYTES) or None
        submission.status = JobStatus.COMPLETED
        submission.judged_at = utcnow()

        await SimilarityService(db, self.settings).index_and_compare(submission, kind)
        self._emit_judged(db, submission)
        await db.commit()

    async def _finish_without_cases(self, db: AsyncSession, submission: Submission, message: str) -> None:
        await db.execute(delete(SubmissionResult).where(SubmissionResult.submission_id == submission.id))
        submission.status = JobStatus.COMPLETED
        submission.verdict = Verdict.INTERNAL_ERROR
        submission.message = message
        submission.judged_at = utcnow()
        self._emit_judged(db, submission)
        await db.commit()

    # ------------------------------------------------------------------ shared

    def _retry_or_give_up(self, job: Run | Submission, message: str) -> None:
        """The engine failed, not the program: try again later, and only give up after JOB_MAX_ATTEMPTS."""
        if job.attempts >= self.settings.JOB_MAX_ATTEMPTS:
            if isinstance(job, Run):
                self._finish_run(job, ExecutionResult(Outcome.INTERNAL_ERROR, message=_clip(message, 500)))
            else:
                job.status = JobStatus.COMPLETED
                job.verdict = Verdict.INTERNAL_ERROR
                job.message = _clip(message, 500)
                job.judged_at = utcnow()
            return
        job.status = JobStatus.QUEUED
        job.available_at = utcnow() + timedelta(seconds=min(2**job.attempts, _MAX_BACKOFF_SECONDS))

    @staticmethod
    def _emit_judged(db: AsyncSession, submission: Submission) -> None:
        """Tell the rest of the platform (assessment-service grades attempts from this)."""
        write_event(
            db,
            event_type="submission.judged",
            aggregate_id=submission.id,
            payload={
                "submission_id": str(submission.public_id),
                "problem_id": str(submission.problem_public_id),
                "user_id": str(submission.user_id),
                "organization_id": str(submission.organization_id) if submission.organization_id else None,
                "language": submission.language_code,
                "verdict": submission.verdict,
                "passed": submission.passed_count,
                "total": submission.total_count,
                "score": submission.score,
                "time_ms": submission.time_ms,
                "memory_kb": submission.memory_kb,
                "reference": submission.reference,
                "flagged": submission.flagged,
                "similarity_percent": submission.similarity_percent,
                "similar_to_submission_id": str(submission.similar_to_public_id) if submission.similar_to_public_id else None,
            },
        )

