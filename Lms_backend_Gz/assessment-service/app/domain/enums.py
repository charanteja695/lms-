"""Enums stored as plain strings (not native DB enums) so new values don't need a type migration."""

from enum import StrEnum


class QuestionType(StrEnum):
    """docs/PRODUCT.md §5.1 question types."""

    MCQ_SINGLE = "mcq_single"
    MCQ_MULTI = "mcq_multi"
    TRUE_FALSE = "true_false"
    FILL_IN = "fill_in"
    MATCH = "match"
    ORDERING = "ordering"
    CODING = "coding"
    SQL = "sql"
    SUBJECTIVE = "subjective"
    FILE_SUBMISSION = "file_submission"


AUTO_GRADED_TYPES = frozenset(
    {
        QuestionType.MCQ_SINGLE,
        QuestionType.MCQ_MULTI,
        QuestionType.TRUE_FALSE,
        QuestionType.FILL_IN,
        QuestionType.MATCH,
        QuestionType.ORDERING,
    }
)
JUDGED_TYPES = frozenset({QuestionType.CODING, QuestionType.SQL})  # graded by code-execution-service
MANUAL_TYPES = frozenset({QuestionType.SUBJECTIVE, QuestionType.FILE_SUBMISSION})
# Negative marking only punishes guessing on questions that can be guessed.
NEGATIVE_MARKING_TYPES = frozenset(
    {QuestionType.MCQ_SINGLE, QuestionType.MCQ_MULTI, QuestionType.TRUE_FALSE, QuestionType.FILL_IN}
)


class QuestionStatus(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"  # never picked for a new paper; attempts already taken keep their pinned version


class VersionStatus(StrEnum):
    """draft -> in_review -> published (immutable) -> superseded, mirroring the content lifecycle (§3.2)."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


class Bloom(StrEnum):
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class TagType(StrEnum):
    SKILL = "skill"
    TOPIC = "topic"
    TAG = "tag"


class TestKind(StrEnum):
    TOPIC = "topic"
    MODULE = "module"
    FINAL = "final"  # the proctored course test: pass -> certificate
    PRACTICE = "practice"
    HIRING = "hiring"  # an employer's online assessment


class TestStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"  # frozen: students may attempt it, authors can no longer edit
    RETIRED = "retired"


class TargetType(StrEnum):
    TOPIC = "topic"
    MODULE = "module"
    COURSE = "course"  # a final test


class TimeMode(StrEnum):
    OVERALL = "overall"
    PER_SECTION = "per_section"


class ResultVisibility(StrEnum):
    IMMEDIATE = "immediate"  # as soon as grading finishes
    AFTER_WINDOW = "after_window"  # when the scheduled window closes
    MANUAL = "manual"  # when staff release the results


class ReviewPolicy(StrEnum):
    NONE = "none"  # the score only
    ANSWERS = "answers"  # correct answers and explanations once results are visible


class ProctoringLevel(StrEnum):
    NONE = "none"
    BASIC = "basic"
    STRICT = "strict"


class ScoreCounting(StrEnum):
    HIGHEST = "highest"  # the best attempt counts (final-test default)
    LATEST = "latest"


class SlotType(StrEnum):
    FIXED = "fixed"  # one named question
    POOL = "pool"  # ``count`` questions drawn per student from those matching the criteria


class AttemptStatus(StrEnum):
    """docs/PRODUCT.md §5.1 attempt lifecycle."""

    NOT_STARTED = "not_started"  # paper prepared (waiting room), clock not running
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"  # by staff or the proctor; the clock is stopped
    SUBMITTED = "submitted"  # by the student, on timeout or by a proctor; waiting for a grader
    GRADING = "grading"  # objective answers scored; coding/manual answers outstanding
    GRADED = "graded"


class SubmitReason(StrEnum):
    MANUAL = "manual"
    TIMEOUT = "timeout"
    TERMINATED = "terminated"


class IntegrityStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    CLEAR = "clear"
    FLAGGED = "flagged"
    UNDER_REVIEW = "under_review"
    REVIEWED_OK = "reviewed_ok"
    INVALIDATED = "invalidated"


INTEGRITY_PASSING = frozenset({IntegrityStatus.NOT_REQUIRED, IntegrityStatus.CLEAR, IntegrityStatus.REVIEWED_OK})


class AttemptResult(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    INVALIDATED = "invalidated"


class GradingStatus(StrEnum):
    AUTO_GRADED = "auto_graded"
    PENDING_JUDGE = "pending_judge"
    PENDING_MANUAL = "pending_manual"
    MANUAL_GRADED = "manual_graded"


class CodingStatus(StrEnum):
    PENDING = "pending"  # not yet sent to code-execution-service
    DISPATCHED = "dispatched"  # queued there; the verdict arrives as submission.judged
    JUDGED = "judged"
    FAILED = "failed"  # gave up; graded 0 and flagged for a human


class IdempotentScope(StrEnum):
    QUESTION = "question"
    TEST = "test"
    ATTEMPT = "attempt"
    IMPORT = "import"
