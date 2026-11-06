"""Enums stored as plain strings (not native DB enums) so new values don't need a type migration."""

from enum import IntEnum, StrEnum


class Verdict(StrEnum):
    """The outcome of a run or a test case (docs/PRODUCT.md §5.2)."""

    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    RUNTIME_ERROR = "runtime_error"
    COMPILATION_ERROR = "compilation_error"
    OUTPUT_LIMIT_EXCEEDED = "output_limit_exceeded"
    INTERNAL_ERROR = "internal_error"


class JobStatus(StrEnum):
    """Lifecycle of a run or submission on the queue."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"


class Priority(IntEnum):
    """Queue lanes, highest first: a proctored exam never waits behind practice (docs/PRODUCT.md §5.2)."""

    PRACTICE = 0  # runs with custom input
    SUBMISSION = 1  # graded practice submissions
    EXAM = 2  # submissions made inside an exam, only via the internal endpoint


class LanguageKind(StrEnum):
    PROGRAM = "program"  # compiled/interpreted source, judged on stdin/stdout
    SQL = "sql"  # one query, judged on its result set


class ProblemType(StrEnum):
    CODE = "code"
    SQL = "sql"


class ProblemStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"  # frozen: students can submit, authors can no longer edit
    RETIRED = "retired"


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class CompareMode(StrEnum):
    EXACT = "exact"  # byte for byte
    TRIM = "trim"  # ignore trailing whitespace on each line and trailing blank lines
    TOKEN = "token"  # ignore all whitespace differences
    FLOAT = "float"  # tokens, numbers compared within a tolerance
    ROWS_ORDERED = "rows_ordered"  # SQL result rows must match in order
    ROWS_UNORDERED = "rows_unordered"  # SQL result rows must match as a set of rows


class IdempotentScope(StrEnum):
    RUN = "run"
    SUBMISSION = "submission"
