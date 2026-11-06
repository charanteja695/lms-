"""Chooses the engine for a language: SQL dialects run on their own database engines, everything else on
the configured program engine (Judge0, or the local development engine)."""

from app.core.config import Settings
from app.domain.enums import LanguageKind
from app.engines.base import EngineError, ExecutionEngine, ExecutionRequest, ExecutionResult
from app.engines.judge0 import Judge0Engine
from app.engines.local import LocalEngine
from app.engines.sql_postgres import PostgresSqlEngine
from app.engines.sql_sqlite import SqliteEngine


class RoutingEngine:
    def __init__(self, program_engine: ExecutionEngine, sql_engines: dict[str, ExecutionEngine]) -> None:
        self.program_engine = program_engine
        self.sql_engines = sql_engines

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if request.language.kind == LanguageKind.SQL:
            engine = self.sql_engines.get(request.language.code)
            if engine is None:
                raise EngineError(f"No SQL engine is configured for {request.language.code}")
            return await engine.execute(request)
        return await self.program_engine.execute(request)

    async def aclose(self) -> None:
        close = getattr(self.program_engine, "aclose", None)
        if close is not None:
            await close()


def build_engine(settings: Settings) -> RoutingEngine:
    program_engine: ExecutionEngine = Judge0Engine(settings) if settings.EXECUTION_ENGINE == "judge0" else LocalEngine()
    sql_engines: dict[str, ExecutionEngine] = {"sqlite": SqliteEngine(settings.SQL_MAX_ROWS)}
    if settings.SQL_POSTGRES_DSN:
        sql_engines["postgresql"] = PostgresSqlEngine(settings.SQL_POSTGRES_DSN, settings.SQL_MAX_ROWS)
    return RoutingEngine(program_engine, sql_engines)
