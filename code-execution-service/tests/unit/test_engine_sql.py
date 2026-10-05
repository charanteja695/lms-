"""The SQL dialect engines: SQLite (in-process) and PostgreSQL (a real embedded server via pgserver)."""

import asyncio
from pathlib import Path

import pytest

from app.domain.enums import LanguageKind
from app.engines.base import EngineError, ExecutionRequest, LanguageSpec, Limits, Outcome
from app.engines.sql_format import format_result
from app.engines.sql_postgres import PostgresSqlEngine
from app.engines.sql_sqlite import SqliteEngine

SETUP = """
CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT, marks REAL);
INSERT INTO students VALUES (1, 'Asha', 91.5), (2, 'Ravi', 78), (3, 'Meena', NULL);
"""
LIMITS = Limits(cpu_time_s=2, wall_time_s=3, memory_mb=64, output_bytes=65_536)
SQLITE = LanguageSpec("sqlite", LanguageKind.SQL, None, "query.sql")
POSTGRES = LanguageSpec("postgresql", LanguageKind.SQL, None, "query.sql")


def test_result_format_is_a_header_and_csv_rows() -> None:
    assert format_result(["id", "name"], [(1, "Asha"), (2, None)]) == "id,name\n1,Asha\n2,NULL\n"
    assert format_result(["v"], [("a,b",), (True,), (b"\x01",)]) == 'v\n"a,b"\ntrue\n0x01\n'
    assert format_result([], []) == ""


# ---------------------------------------------------------------------------------------------- SQLite


def _sqlite(query: str, *, setup: str = SETUP, limits: Limits = LIMITS, max_rows: int = 1_000):
    return SqliteEngine(max_rows).execute(ExecutionRequest(SQLITE, query, "", limits, setup))


async def test_sqlite_returns_the_result_set_as_canonical_text() -> None:
    result = await _sqlite("SELECT id, name FROM students WHERE marks > 80 ORDER BY id")
    assert result.outcome == Outcome.OK
    assert result.stdout == "id,name\n1,Asha\n"


async def test_sqlite_nulls_and_numbers() -> None:
    result = await _sqlite("SELECT name, marks FROM students ORDER BY id")
    assert result.stdout == "name,marks\nAsha,91.5\nRavi,78.0\nMeena,NULL\n"


async def test_sqlite_syntax_error_and_missing_table_are_compilation_errors() -> None:
    for query in ("SELEC 1", "SELECT * FROM nope", "SELECT missing FROM students"):
        result = await _sqlite(query)
        assert result.outcome == Outcome.COMPILATION_ERROR, query
        assert result.compile_output


async def test_sqlite_refuses_more_than_one_statement() -> None:
    result = await _sqlite("SELECT 1; SELECT 2")
    assert result.outcome == Outcome.COMPILATION_ERROR


async def test_sqlite_a_runaway_query_hits_the_time_limit() -> None:
    forever = "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r) SELECT count(*) FROM r"
    result = await _sqlite(forever, limits=Limits(1, 0.5, 64, 65_536))
    assert result.outcome == Outcome.TIME_LIMIT_EXCEEDED


@pytest.mark.parametrize(
    "attack",
    ["ATTACH DATABASE '/tmp/x.db' AS x", "PRAGMA writable_schema = 1", "SELECT load_extension('evil')", "SELECT readfile('/etc/passwd')"],
)
async def test_sqlite_blocks_attach_pragma_and_file_functions(attack: str) -> None:
    result = await _sqlite(attack)
    assert result.outcome in {Outcome.COMPILATION_ERROR, Outcome.RUNTIME_ERROR}
    assert "not authorized" in result.message or "no such function" in result.message


async def test_sqlite_too_many_rows_is_an_output_limit() -> None:
    result = await _sqlite("WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r WHERE n < 50) SELECT n FROM r", max_rows=10)
    assert result.outcome == Outcome.OUTPUT_LIMIT_EXCEEDED


async def test_sqlite_a_database_that_grows_too_large_is_a_memory_limit() -> None:
    setup = "CREATE TABLE big (b BLOB); INSERT INTO big VALUES (zeroblob(100))"
    grow = "INSERT INTO big SELECT zeroblob(4000) FROM (WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r WHERE n < 100000) SELECT n FROM r)"
    result = await _sqlite(grow, setup=setup, limits=Limits(5, 20, 1, 65_536))
    assert result.outcome == Outcome.MEMORY_LIMIT_EXCEEDED


async def test_sqlite_a_broken_setup_script_is_an_internal_error_not_the_students_fault() -> None:
    result = await _sqlite("SELECT 1", setup="THIS IS NOT SQL")
    assert result.outcome == Outcome.INTERNAL_ERROR


async def test_sqlite_each_run_starts_from_a_clean_database() -> None:
    await _sqlite("CREATE TABLE leak (x INT)", setup="")
    result = await _sqlite("SELECT * FROM leak", setup="")
    assert result.outcome == Outcome.COMPILATION_ERROR  # the previous run's table is gone


# ------------------------------------------------------------------------------------------- PostgreSQL


@pytest.fixture(scope="module")
def sandbox_dsn(tmp_path_factory) -> str:
    """A real PostgreSQL with the documented sandbox role (runtimes/sql/postgres_sandbox.sql) applied as written."""
    pgserver = pytest.importorskip("pgserver")
    import asyncpg

    server = pgserver.get_server(tmp_path_factory.mktemp("pg_sandbox"), cleanup_mode="delete")
    script = (Path(__file__).resolve().parents[2] / "runtimes" / "sql" / "postgres_sandbox.sql").read_text(encoding="utf-8")
    part1, part2 = script.split("-- @@ part 2")
    part2 = part2.split(chr(10), 1)[1]  # the rest of the marker comment line
    admin_uri = server.get_uri()

    def statements(sql: str) -> list[str]:
        """One at a time, like psql: CREATE DATABASE cannot run inside a multi-statement transaction."""
        body = chr(10).join(line for line in sql.splitlines() if not line.strip().startswith("--"))
        return [statement.strip() for statement in body.split(";") if statement.strip()]

    async def apply() -> None:
        for database, sql in (("postgres", part1.replace("CHANGE-ME", "pw")), ("lms_sandbox", part2)):
            connection = await asyncpg.connect(admin_uri.rsplit("/", 1)[0] + "/" + database)
            try:
                for statement in statements(sql):
                    await connection.execute(statement)
            finally:
                await connection.close()

    asyncio.run(apply())
    yield admin_uri.replace("postgres:@", "lms_sandbox:pw@").rsplit("/", 1)[0] + "/lms_sandbox"
    server.cleanup()


def _postgres(dsn: str, query: str, *, setup: str = SETUP, limits: Limits = LIMITS):
    return PostgresSqlEngine(dsn, 1_000).execute(ExecutionRequest(POSTGRES, query, "", limits, setup))


PG_SETUP = """
CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT, marks NUMERIC);
INSERT INTO students VALUES (1, 'Asha', 91.5), (2, 'Ravi', 78), (3, 'Meena', NULL);
"""


async def test_postgres_returns_the_result_set(sandbox_dsn: str) -> None:
    result = await _postgres(sandbox_dsn, "SELECT id, name, marks FROM students ORDER BY id", setup=PG_SETUP)
    assert result.outcome == Outcome.OK
    assert result.stdout == "id,name,marks\n1,Asha,91.5\n2,Ravi,78\n3,Meena,NULL\n"


async def test_postgres_errors_are_classified(sandbox_dsn: str) -> None:
    syntax = await _postgres(sandbox_dsn, "SELEC 1", setup="")
    missing = await _postgres(sandbox_dsn, "SELECT * FROM nope", setup="")
    runtime = await _postgres(sandbox_dsn, "SELECT 1 / 0", setup="")
    two = await _postgres(sandbox_dsn, "SELECT 1; SELECT 2", setup="")
    assert [r.outcome for r in (syntax, missing, two)] == [Outcome.COMPILATION_ERROR] * 3
    assert runtime.outcome == Outcome.RUNTIME_ERROR and "division by zero" in runtime.message


async def test_postgres_a_slow_query_hits_the_time_limit(sandbox_dsn: str) -> None:
    result = await _postgres(sandbox_dsn, "SELECT pg_sleep(10)", setup="", limits=Limits(1, 0.6, 64, 65_536))
    assert result.outcome == Outcome.TIME_LIMIT_EXCEEDED


async def test_postgres_nothing_a_run_creates_survives_it(sandbox_dsn: str) -> None:
    created = await _postgres(sandbox_dsn, "SELECT count(*) AS n FROM students", setup=PG_SETUP)
    assert created.stdout == "n\n3\n"
    later = await _postgres(sandbox_dsn, "SELECT count(*) FROM students", setup="")
    assert later.outcome == Outcome.COMPILATION_ERROR  # the table existed only inside the first run


async def test_postgres_concurrent_runs_do_not_see_each_other(sandbox_dsn: str) -> None:
    async def run(value: int):
        setup = f"CREATE TABLE mine (v INT); INSERT INTO mine VALUES ({value})"  # noqa: S608
        return await _postgres(sandbox_dsn, "SELECT v FROM mine", setup=setup)

    results = await asyncio.gather(*(run(n) for n in range(1, 9)))
    assert [r.stdout for r in results] == [f"v\n{n}\n" for n in range(1, 9)]


@pytest.mark.parametrize(
    "attack",
    [
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT * FROM pg_shadow",
        "SELECT pg_ls_dir('/')",
        "CREATE TABLE public.escape (x INT)",
        "SELECT lo_import('/etc/passwd')",
        "COPY (SELECT 1) TO PROGRAM 'echo pwned'",
    ],
)
async def test_postgres_the_sandbox_role_cannot_reach_the_server_or_other_schemas(sandbox_dsn: str, attack: str) -> None:
    result = await _postgres(sandbox_dsn, attack, setup="")
    assert result.outcome in {Outcome.COMPILATION_ERROR, Outcome.RUNTIME_ERROR}, attack


async def test_postgres_an_unreachable_sandbox_is_an_engine_error() -> None:
    with pytest.raises(EngineError):
        await _postgres("postgresql://lms_sandbox:pw@127.0.0.1:1/lms_sandbox", "SELECT 1", setup="")


async def test_postgres_a_broken_setup_script_is_an_internal_error(sandbox_dsn: str) -> None:
    result = await _postgres(sandbox_dsn, "SELECT 1", setup="THIS IS NOT SQL")
    assert result.outcome == Outcome.INTERNAL_ERROR
