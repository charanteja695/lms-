"""SQLite dialect. Each run gets its own in-memory database that disappears with the connection.

Containment: no ATTACH/DETACH/PRAGMA and no file-touching functions (an authorizer), a wall-clock deadline
enforced from SQLite's progress handler (so a runaway recursive query stops), a page cap standing in for a
memory limit, and a row cap on what a query may return. One statement per query: SQLite itself refuses more.
"""

import asyncio
import sqlite3
import time
from typing import Any

from app.engines.base import ExecutionRequest, ExecutionResult, Outcome
from app.engines.sql_format import format_result

_PAGE_SIZE = 4_096
_DENIED_ACTIONS = {sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA}
_DENIED_FUNCTIONS = {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer"}


def _authorizer(action: int, arg1: Any, arg2: Any, db_name: Any, source: Any) -> int:
    if action in _DENIED_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and str(arg2 or "").lower() in _DENIED_FUNCTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


class SqliteEngine:
    def __init__(self, max_rows: int) -> None:
        self.max_rows = max_rows

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return await asyncio.to_thread(self._run, request)

    def _run(self, request: ExecutionRequest) -> ExecutionResult:
        started = time.monotonic()
        deadline = started + request.limits.wall_time_s
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute(f"PRAGMA max_page_count = {request.limits.memory_mb * 1024 * 1024 // _PAGE_SIZE}")
            if request.setup:
                connection.executescript(request.setup)  # trusted: written by staff, run before the lock-down
            connection.set_authorizer(_authorizer)
            connection.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 1_000)

            try:
                cursor = connection.execute(request.source)
            except sqlite3.Error as exc:
                return self._failure(exc, started, compile_phase=True)
            try:
                columns = [column[0] for column in cursor.description or ()]
                rows = cursor.fetchmany(self.max_rows + 1)
            except sqlite3.Error as exc:
                return self._failure(exc, started, compile_phase=False)

            elapsed = int((time.monotonic() - started) * 1000)
            if len(rows) > self.max_rows:
                return ExecutionResult(Outcome.OUTPUT_LIMIT_EXCEEDED, time_ms=elapsed, message=f"More than {self.max_rows} rows")
            stdout = format_result(columns, rows)
            if len(stdout.encode()) > request.limits.output_bytes:
                return ExecutionResult(Outcome.OUTPUT_LIMIT_EXCEEDED, time_ms=elapsed, message="Output limit exceeded")
            return ExecutionResult(Outcome.OK, stdout=stdout, time_ms=elapsed, exit_code=0)
        except sqlite3.Error as exc:  # the trusted setup script failed: an authoring bug, not the student's
            return ExecutionResult(Outcome.INTERNAL_ERROR, message=f"Problem setup failed: {exc}"[:500])
        finally:
            connection.close()

    @staticmethod
    def _failure(exc: sqlite3.Error, started: float, *, compile_phase: bool) -> ExecutionResult:
        elapsed = int((time.monotonic() - started) * 1000)
        message = str(exc)[:500]
        if "interrupted" in message:
            return ExecutionResult(Outcome.TIME_LIMIT_EXCEEDED, time_ms=elapsed, message="Time limit exceeded")
        if "database or disk is full" in message:
            return ExecutionResult(Outcome.MEMORY_LIMIT_EXCEEDED, time_ms=elapsed, message="Memory limit exceeded")
        if compile_phase:
            return ExecutionResult(Outcome.COMPILATION_ERROR, compile_output=message, time_ms=elapsed, message=message)
        return ExecutionResult(Outcome.RUNTIME_ERROR, stderr=message, time_ms=elapsed, message=message)
