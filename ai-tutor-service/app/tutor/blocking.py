"""The tutor is disabled inside graded tests (docs/PRODUCT.md §5.5 "Guardrails")."""

from dataclasses import dataclass
from datetime import datetime, timedelta

# Practice tests are not graded; every other kind (topic, module, final, hiring) is.
UNGRADED_KINDS = frozenset({"practice"})


@dataclass(frozen=True, slots=True)
class OpenAttempt:
    attempt_id: int
    test_kind: str
    deadline_at: datetime | None


def blocking_attempt(attempts: list[OpenAttempt], now: datetime, grace_seconds: int) -> OpenAttempt | None:
    """The graded attempt that currently blocks the tutor, if any. An attempt whose deadline plus ``grace_seconds`` has
    passed no longer blocks: a lost ``attempt.submitted`` event must not lock a student out for good (assessment-service
    submits at the deadline anyway). An attempt with no deadline blocks until it is submitted."""
    for attempt in attempts:
        if attempt.test_kind in UNGRADED_KINDS:
            continue
        if attempt.deadline_at is not None and now > attempt.deadline_at + timedelta(seconds=grace_seconds):
            continue
        return attempt
    return None
