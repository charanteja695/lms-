"""The contract between this service and whatever actually runs code (docs/PRODUCT.md D4).

Everything above this module (queue, judging, API) talks to an ``ExecutionEngine`` and knows nothing
about Judge0, subprocesses or databases, so the engine can be replaced without touching the rest.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.domain.enums import LanguageKind


class Outcome(StrEnum):
    """What happened to one execution, before an expected output is considered."""

    OK = "ok"  # ran to completion, exit code 0
    COMPILATION_ERROR = "compilation_error"
    RUNTIME_ERROR = "runtime_error"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    OUTPUT_LIMIT_EXCEEDED = "output_limit_exceeded"
    INTERNAL_ERROR = "internal_error"  # the engine failed, not the program: worth retrying


class EngineError(Exception):
    """The engine could not be reached or misbehaved. Never the student's fault, so the job is retried
    (up to JOB_MAX_ATTEMPTS) instead of being given a verdict."""


@dataclass(frozen=True, slots=True)
class LanguageSpec:
    code: str
    kind: LanguageKind
    engine_language_id: int | None
    file_name: str
    local_command: tuple[str, ...] | None = None
    compiler_options: str | None = None


@dataclass(frozen=True, slots=True)
class Limits:
    cpu_time_s: float
    wall_time_s: float
    memory_mb: int
    output_bytes: int


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    language: LanguageSpec
    source: str
    stdin: str
    limits: Limits
    setup: str = ""  # SQL only: schema and seed data run before the query, trusted (authored by staff)


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    outcome: Outcome
    stdout: str = ""
    stderr: str = ""
    compile_output: str = ""
    message: str = ""
    time_ms: int | None = None
    memory_kb: int | None = None
    exit_code: int | None = None


class ExecutionEngine(Protocol):
    async def execute(self, request: ExecutionRequest) -> ExecutionResult: ...
