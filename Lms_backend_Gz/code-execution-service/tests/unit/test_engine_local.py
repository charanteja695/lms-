"""The local development engine, with a real Python interpreter (this machine has one)."""

import sys

import pytest

from app.domain.enums import LanguageKind
from app.engines.base import EngineError, ExecutionRequest, LanguageSpec, Limits, Outcome
from app.engines.local import LocalEngine

PYTHON = LanguageSpec("python3", LanguageKind.PROGRAM, 71, "main.py", local_command=("{python}", "{file}"))
LIMITS = Limits(cpu_time_s=2, wall_time_s=5, memory_mb=256, output_bytes=4_096)


def _run(source: str, stdin: str = "", *, language: LanguageSpec = PYTHON, limits: Limits = LIMITS):
    return LocalEngine().execute(ExecutionRequest(language, source, stdin, limits))


async def test_output_and_stdin_round_trip() -> None:
    result = await _run("name = input()\nprint('hello', name)", stdin="Asha\n")
    assert result.outcome == Outcome.OK
    assert result.stdout.strip() == "hello Asha"
    assert result.exit_code == 0
    assert result.time_ms is not None


async def test_a_crash_is_a_runtime_error_with_the_traceback() -> None:
    result = await _run("print('partial')\nraise ValueError('boom')")
    assert result.outcome == Outcome.RUNTIME_ERROR
    assert result.exit_code == 1
    assert "ValueError: boom" in result.stderr
    assert result.stdout.strip() == "partial"


async def test_an_infinite_loop_is_a_time_limit() -> None:
    result = await _run("while True:\n    pass", limits=Limits(1, 0.6, 256, 4_096))
    assert result.outcome == Outcome.TIME_LIMIT_EXCEEDED


async def test_an_output_flood_is_stopped_at_the_limit() -> None:
    result = await _run("while True:\n    print('x' * 1000)", limits=Limits(2, 5, 256, 2_048))
    assert result.outcome == Outcome.OUTPUT_LIMIT_EXCEEDED
    assert len(result.stdout) <= 2_048


async def test_the_program_runs_in_a_scratch_directory_with_a_minimal_environment() -> None:
    result = await _run("import os\nprint(sorted(os.environ)[:0] == [])\nprint('DATABASE_URL' in os.environ)\nprint(os.getcwd())")
    lines = result.stdout.split()
    assert lines[1] == "False"  # the service's secrets are not passed on
    assert "lms-run-" in lines[2]


async def test_reading_stdin_the_program_never_asked_for_does_not_hang_or_fail() -> None:
    result = await _run("print('ignored input')", stdin="x" * 200_000)
    assert result.outcome == Outcome.OK


async def test_a_language_without_a_local_command_is_an_engine_error() -> None:
    java = LanguageSpec("java", LanguageKind.PROGRAM, 62, "Main.java")
    with pytest.raises(EngineError, match="no local command"):
        await _run("class Main {}", language=java)


async def test_a_runtime_that_is_not_installed_is_reported_not_crashed() -> None:
    missing = LanguageSpec("nope", LanguageKind.PROGRAM, None, "main.x", local_command=("definitely-not-installed-xyz", "{file}"))
    result = await _run("x", language=missing)
    assert result.outcome == Outcome.INTERNAL_ERROR
    assert "not installed" in result.message


async def test_the_interpreter_placeholder_is_this_python() -> None:
    result = await _run("import sys\nprint(sys.version_info[:2])")
    assert str(sys.version_info[0]) in result.stdout
