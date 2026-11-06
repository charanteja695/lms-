"""The resource limits a run or a judged case gets. Slower runtimes get proportionally more (the language's
multipliers), so a Python solution is not failed for being Python."""

from app.core.config import Settings
from app.engines.base import Limits
from app.models.language import Language
from app.models.problem import Problem

_WALL_HEADROOM_SECONDS = 1.0  # process start-up and I/O waits do not count as CPU time but do count on the clock


def run_limits(settings: Settings, language: Language) -> Limits:
    return Limits(
        cpu_time_s=settings.RUN_CPU_TIME_SECONDS * language.time_multiplier,
        wall_time_s=settings.RUN_WALL_TIME_SECONDS * language.time_multiplier,
        memory_mb=max(int(settings.RUN_MEMORY_MB * language.memory_multiplier), 16),
        output_bytes=settings.MAX_OUTPUT_BYTES,
    )


def problem_limits(settings: Settings, problem: Problem, language: Language) -> Limits:
    cpu = problem.time_limit_ms / 1000 * language.time_multiplier
    return Limits(
        cpu_time_s=cpu,
        wall_time_s=cpu * 2 + _WALL_HEADROOM_SECONDS,
        memory_mb=max(int(problem.memory_limit_mb * language.memory_multiplier), 16),
        output_bytes=settings.MAX_OUTPUT_BYTES,
    )
