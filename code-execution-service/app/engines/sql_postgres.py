"""PostgreSQL dialect, against a DEDICATED sandbox cluster (never this service's own database).

Each run opens its own connection and one transaction that is always rolled back, with ``search_path``
set to ``pg_temp`` so every object the setup script or the query creates is a session-local temporary
one: nothing persists, and concurrent runs cannot see each other. The connecting role must be a plain
low-privilege role with no rights on any real data — see runtimes/sql/postgres_sandbox.sql, which also sets
the role-level limits (statement_timeout, temp_file_limit, work_mem, connection limit) that a session cannot
raise for itself.

One statement per query: it is prepared, and PostgreSQL refuses a prepared statement holding several.
"""

import time

import asyncpg

from app.engines.base import EngineError, ExecutionRequest, ExecutionResult, Outcome
from app.engines.sql_format import format_result

_QUERY_CANCELED = "57014"  # statement_timeout fired
_OUT_OF_MEMORY = "53200"
_DISK_FULL = "53100"
_CONNECT_TIMEOUT_SECONDS = 5


class PostgresSqlEngine:
    def __init__(self, dsn: str, max_rows: int) -> None:
        self.dsn = dsn
        self.max_rows = max_rows

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        started = time.monotonic()
        try:
            connection = await asyncpg.connect(self.dsn, timeout=_CONNECT_TIMEOUT_SECONDS)
        except (OSError, asyncpg.PostgresError, TimeoutError) as exc:
            raise EngineError(f"SQL sandbox unreachable: {exc}") from exc
        transaction = connection.transaction()
        try:
            await transaction.start()
            timeout_ms = max(int(request.limits.wall_time_s * 1000), 1)
            await connection.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
            await connection.execute("SET LOCAL search_path = pg_temp")
            if request.setup:
                try:
                    await connection.execute(request.setup)  # trusted: written by staff
                except asyncpg.PostgresError as exc:
                    return ExecutionResult(Outcome.INTERNAL_ERROR, message=f"Problem setup failed: {exc}"[:500])
            return await self._query(connection, request, started)
        finally:
            try:
                await transaction.rollback()
            except (asyncpg.PostgresError, asyncpg.InterfaceError):
                pass  # the connection is closed next either way; nothing was committed
            await connection.close()

    async def _query(self, connection: asyncpg.Connection, request: ExecutionRequest, started: float) -> ExecutionResult:
        def elapsed() -> int:
            return int((time.monotonic() - started) * 1000)

        try:
            statement = await connection.prepare(request.source)
        except asyncpg.PostgresError as exc:
            return self._error(exc, elapsed(), compile_phase=True)
        try:
            columns = [attribute.name for attribute in statement.get_attributes()]
            if columns:
                rows = await statement.fetch(timeout=request.limits.wall_time_s)
                rows = rows[: self.max_rows + 1]
            else:
                await statement.fetch(timeout=request.limits.wall_time_s)
                rows = []
        except asyncpg.PostgresError as exc:
            return self._error(exc, elapsed(), compile_phase=False)
        except TimeoutError:
            return ExecutionResult(Outcome.TIME_LIMIT_EXCEEDED, time_ms=elapsed(), message="Time limit exceeded")

        if len(rows) > self.max_rows:
            return ExecutionResult(Outcome.OUTPUT_LIMIT_EXCEEDED, time_ms=elapsed(), message=f"More than {self.max_rows} rows")
        stdout = format_result(columns, [tuple(row.values()) for row in rows])
        if len(stdout.encode()) > request.limits.output_bytes:
            return ExecutionResult(Outcome.OUTPUT_LIMIT_EXCEEDED, time_ms=elapsed(), message="Output limit exceeded")
        return ExecutionResult(Outcome.OK, stdout=stdout, time_ms=elapsed(), exit_code=0)

    @staticmethod
    def _error(exc: asyncpg.PostgresError, elapsed_ms: int, *, compile_phase: bool) -> ExecutionResult:
        message = str(exc)[:500]
        sqlstate = getattr(exc, "sqlstate", None)
        if sqlstate == _QUERY_CANCELED:
            return ExecutionResult(Outcome.TIME_LIMIT_EXCEEDED, time_ms=elapsed_ms, message="Time limit exceeded")
        if sqlstate in {_OUT_OF_MEMORY, _DISK_FULL}:
            return ExecutionResult(Outcome.MEMORY_LIMIT_EXCEEDED, time_ms=elapsed_ms, message="Memory limit exceeded")
        if compile_phase:
            return ExecutionResult(Outcome.COMPILATION_ERROR, compile_output=message, time_ms=elapsed_ms, message=message)
        return ExecutionResult(Outcome.RUNTIME_ERROR, stderr=message, time_ms=elapsed_ms, message=message)
