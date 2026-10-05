"""Development and test engine: runs the program as a plain subprocess of this machine.

There is NO isolation here — no memory limit, no network block, no filesystem restriction, and the
code runs as the service's own user. It exists so the whole pipeline can be exercised without Judge0,
and Settings refuses to start staging/production with it (EXECUTION_ENGINE must be judge0 there).
Only languages that declare a ``local_command`` in runtimes/languages.json can run.
"""

import asyncio
import contextlib
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from app.engines.base import EngineError, ExecutionRequest, ExecutionResult, Outcome

_PLACEHOLDERS = {"{python}": sys.executable}
_SAFE_ENV_KEYS = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "LANG")


def _resolve(part: str, file_name: str) -> str:
    if part == "{file}":
        return file_name
    if part in _PLACEHOLDERS:
        return _PLACEHOLDERS[part]
    return shutil.which(part) or part


def _environment() -> dict[str, str]:
    return {key: os.environ[key] for key in _SAFE_ENV_KEYS if key in os.environ}


async def _read_capped(stream: asyncio.StreamReader, cap: int) -> tuple[bytes, bool]:
    """Read up to ``cap`` bytes; the flag says the program wrote more than that."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await stream.read(65_536)
        if not chunk:
            return b"".join(chunks), False
        if total + len(chunk) > cap:
            chunks.append(chunk[: cap - total])
            return b"".join(chunks), True
        chunks.append(chunk)
        total += len(chunk)


class LocalEngine:
    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        command = request.language.local_command
        if not command:
            raise EngineError(f"{request.language.code} has no local command; use EXECUTION_ENGINE=judge0")
        argv = [_resolve(part, request.language.file_name) for part in command]
        if shutil.which(argv[0]) is None:  # also accepts an absolute path
            return ExecutionResult(Outcome.INTERNAL_ERROR, message=f"{command[0]} is not installed on this machine")

        with tempfile.TemporaryDirectory(prefix="lms-run-") as workdir:
            await asyncio.to_thread(Path(workdir, request.language.file_name).write_text, request.source, encoding="utf-8")
            started = time.monotonic()
            process = await asyncio.create_subprocess_exec(
                *argv,
                cwd=workdir,
                env=_environment(),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                return await asyncio.wait_for(
                    self._collect(process, request, started), timeout=request.limits.wall_time_s
                )
            except TimeoutError:
                await self._kill(process)
                return ExecutionResult(
                    Outcome.TIME_LIMIT_EXCEEDED, time_ms=int(request.limits.wall_time_s * 1000), message="Time limit exceeded"
                )

    async def _collect(self, process: asyncio.subprocess.Process, request: ExecutionRequest, started: float) -> ExecutionResult:
        assert process.stdin and process.stdout and process.stderr
        cap = request.limits.output_bytes
        stdout_task = asyncio.create_task(_read_capped(process.stdout, cap))
        stderr_task = asyncio.create_task(_read_capped(process.stderr, cap))
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            process.stdin.write(request.stdin.encode())
            await process.stdin.drain()
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            process.stdin.close()

        # Kill the moment either stream overflows: waiting for both to finish would hang on a silent one.
        done, _ = await asyncio.wait({stdout_task, stderr_task}, return_when=asyncio.FIRST_COMPLETED)
        if any(task.result()[1] for task in done):
            await self._kill(process)
        (stdout, stdout_over), (stderr, stderr_over) = await asyncio.gather(stdout_task, stderr_task)
        if stdout_over or stderr_over:
            await self._kill(process)
        exit_code = await process.wait()
        elapsed_ms = int((time.monotonic() - started) * 1000)
        text_out, text_err = stdout.decode(errors="replace"), stderr.decode(errors="replace")

        if stdout_over or stderr_over:
            return ExecutionResult(
                Outcome.OUTPUT_LIMIT_EXCEEDED, text_out, text_err, time_ms=elapsed_ms, exit_code=exit_code, message="Output limit exceeded"
            )
        outcome = Outcome.OK if exit_code == 0 else Outcome.RUNTIME_ERROR
        return ExecutionResult(outcome, text_out, text_err, time_ms=elapsed_ms, exit_code=exit_code)

    @staticmethod
    async def _kill(process: asyncio.subprocess.Process) -> None:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(process.wait(), timeout=2)
