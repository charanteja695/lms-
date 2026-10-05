"""The recovery path for two requests that carry one Idempotency-Key at the same instant.

Both check for the key, both find nothing, both insert: the database's unique constraint lets exactly one win, and
the loser must quietly return the winner's resource instead of failing. Real concurrency rarely lines up exactly, so
these tests force it: the first lookup is made to miss even though the key already exists."""

import pytest
from sqlalchemy import func, select

from app.core.security import AccessTokenClaims
from app.domain.enums import Priority
from app.models.idempotency_key import IdempotencyKey
from app.models.problem import Problem
from app.models.run import Run
from app.models.submission import Submission
from app.schemas.run import RunCreate
from app.services.idempotency_service import IdempotencyService
from app.services.rate_limiter import RateLimiter
from app.services.run_service import RunService
from app.services.submission_service import SubmissionService
from tests.conftest import ORG_A, STUDENT, SUM_SOLUTION, ProblemFactory, make_claims


@pytest.fixture
def misses_once(monkeypatch):
    """Make the first idempotency lookup report 'no such key', as if the other request had not committed yet."""
    real_find = IdempotencyService.find
    state = {"calls": 0}

    async def find(self, *args, **kwargs):
        state["calls"] += 1
        return None if state["calls"] == 1 else await real_find(self, *args, **kwargs)

    monkeypatch.setattr(IdempotencyService, "find", find)
    return state


async def test_a_run_that_loses_the_race_returns_the_winners_run(sessionmaker, settings, misses_once) -> None:
    claims: AccessTokenClaims = make_claims(user_id=STUDENT, role="student", organization_id=ORG_A, scopes=())
    limiter = RateLimiter(None, enabled=False)  # type: ignore[arg-type]
    data = RunCreate(language="python3", source="print(1)")

    async with sessionmaker() as db:
        winner = await RunService(db, settings, limiter).create(claims, data, "race-key-run-1")
    misses_once["calls"] = 0  # the next lookup will miss even though the key exists
    async with sessionmaker() as db:
        loser = await RunService(db, settings, limiter).create(claims, data, "race-key-run-1")

    assert loser.public_id == winner.public_id
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count()).select_from(Run))).scalar_one() == 1
        assert (await db.execute(select(func.count()).select_from(IdempotencyKey))).scalar_one() == 1


async def test_a_submission_that_loses_the_race_returns_the_winners_submission(sessionmaker, settings, make_problem: ProblemFactory, misses_once) -> None:
    problem_id = await make_problem()
    async with sessionmaker() as db:
        problem = (await db.execute(select(Problem).where(Problem.public_id == problem_id))).scalar_one()
        misses_once["calls"] = 0
        winner = await SubmissionService(db, settings).create(
            user_id=STUDENT, organization_id=ORG_A, problem=problem, language_code="python3", source=SUM_SOLUTION, priority=Priority.SUBMISSION, key="race-key-sub-1"
        )
    misses_once["calls"] = 0
    async with sessionmaker() as db:
        problem = (await db.execute(select(Problem).where(Problem.public_id == problem_id))).scalar_one()
        loser = await SubmissionService(db, settings).create(
            user_id=STUDENT, organization_id=ORG_A, problem=problem, language_code="python3", source=SUM_SOLUTION, priority=Priority.SUBMISSION, key="race-key-sub-1"
        )

    assert loser.public_id == winner.public_id
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count()).select_from(Submission))).scalar_one() == 1


async def test_a_genuine_integrity_error_that_is_not_a_key_race_is_not_swallowed(sessionmaker, settings, monkeypatch) -> None:
    """If the insert fails and there is no earlier request to fall back on, the error must surface, not vanish."""
    claims = make_claims(user_id=STUDENT, role="student", organization_id=ORG_A, scopes=())
    limiter = RateLimiter(None, enabled=False)  # type: ignore[arg-type]
    monkeypatch.setattr("app.services.run_service.new_public_id", lambda: 12345)  # two runs forced onto one public id

    async with sessionmaker() as db:
        await RunService(db, settings, limiter).create(claims, RunCreate(language="python3", source="print(1)"), None)
    async with sessionmaker() as db:
        with pytest.raises(Exception, match="UNIQUE|unique|Integrity"):
            await RunService(db, settings, limiter).create(claims, RunCreate(language="python3", source="print(2)"), "key-with-no-twin-1")
