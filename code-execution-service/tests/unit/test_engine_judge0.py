"""The Judge0 engine against a mocked Judge0 API. There is no Judge0 on the development machine, so this
checks OUR side of the contract (request shape, status mapping, error handling), not Judge0 itself."""

import base64
import json

import httpx
import pytest
import respx

from app.core.config import Settings
from app.domain.enums import LanguageKind
from app.engines.base import EngineError, ExecutionRequest, LanguageSpec, Limits, Outcome
from app.engines.judge0 import Judge0Engine

CPP = LanguageSpec("cpp20", LanguageKind.PROGRAM, 54, "main.cpp", compiler_options="-std=c++20 -O2")
LIMITS = Limits(cpu_time_s=2.0, wall_time_s=5.0, memory_mb=256, output_bytes=65_536)


def b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def judge0_reply(status_id: int, **fields: object) -> dict:
    return {"status": {"id": status_id, "description": "x"}, "stdout": None, "stderr": None, "compile_output": None,
            "message": None, "time": None, "memory": None, "exit_code": None, **fields}


@pytest.fixture
def judge0():
    settings = Settings(ENVIRONMENT="test", JUDGE0_URL="http://judge0.test", JUDGE0_AUTH_TOKEN="secret-token")
    with respx.mock(base_url="http://judge0.test", assert_all_called=False) as router:
        yield Judge0Engine(settings), router


def _request(source: str = "int main(){}", stdin: str = "1 2") -> ExecutionRequest:
    return ExecutionRequest(CPP, source, stdin, LIMITS)


async def test_the_request_carries_code_input_limits_options_and_the_auth_token(judge0) -> None:
    engine, router = judge0
    route = router.post("/submissions").mock(return_value=httpx.Response(201, json=judge0_reply(3, stdout=b64("3\n"), time="0.012", memory=2048, exit_code=0)))

    result = await engine.execute(_request(source="int main(){return 0;}", stdin="1 2"))

    sent = route.calls.last.request
    body = json.loads(sent.content)
    assert dict(sent.url.params) == {"base64_encoded": "true", "wait": "true"}
    assert sent.headers["X-Auth-Token"] == "secret-token"
    assert base64.b64decode(body["source_code"]).decode() == "int main(){return 0;}"
    assert base64.b64decode(body["stdin"]).decode() == "1 2"
    assert body["language_id"] == 54
    assert body["compiler_options"] == "-std=c++20 -O2"
    assert body["cpu_time_limit"] == 2.0 and body["wall_time_limit"] == 5.0
    assert body["memory_limit"] == 256 * 1024  # Judge0 wants KB
    assert body["max_file_size"] == 64  # KB
    assert result.outcome == Outcome.OK and result.stdout == "3\n"
    assert result.time_ms == 12 and result.memory_kb == 2048 and result.exit_code == 0


@pytest.mark.parametrize(
    ("status_id", "extra", "outcome"),
    [
        (3, {}, Outcome.OK),
        (5, {"time": "2.0"}, Outcome.TIME_LIMIT_EXCEEDED),
        (6, {"compile_output": b64("error: expected ';'")}, Outcome.COMPILATION_ERROR),
        (7, {"memory": 1000}, Outcome.RUNTIME_ERROR),  # SIGSEGV, well under the memory limit
        (9, {}, Outcome.RUNTIME_ERROR),  # SIGFPE
        (11, {"exit_code": 1, "stderr": b64("boom")}, Outcome.RUNTIME_ERROR),  # non-zero exit
        (8, {}, Outcome.OUTPUT_LIMIT_EXCEEDED),  # SIGXFSZ: wrote past max_file_size
        (13, {"message": b64("isolate failed")}, Outcome.INTERNAL_ERROR),
    ],
)
async def test_judge0_statuses_become_outcomes(judge0, status_id: int, extra: dict, outcome: Outcome) -> None:
    engine, router = judge0
    router.post("/submissions").mock(return_value=httpx.Response(201, json=judge0_reply(status_id, **extra)))
    assert (await engine.execute(_request())).outcome == outcome


async def test_a_crash_near_the_memory_limit_is_a_memory_limit_verdict(judge0) -> None:
    engine, router = judge0
    router.post("/submissions").mock(return_value=httpx.Response(201, json=judge0_reply(7, memory=256 * 1024)))
    assert (await engine.execute(_request())).outcome == Outcome.MEMORY_LIMIT_EXCEEDED


async def test_output_streams_are_decoded(judge0) -> None:
    engine, router = judge0
    router.post("/submissions").mock(
        return_value=httpx.Response(201, json=judge0_reply(11, stdout=b64("partial"), stderr=b64("trace"), exit_code=1))
    )
    result = await engine.execute(_request())
    assert (result.stdout, result.stderr) == ("partial", "trace")


@pytest.mark.parametrize("failure", [httpx.Response(500), httpx.Response(200, text="not json"), httpx.ConnectError("refused"), httpx.ReadTimeout("slow")])
async def test_an_unreachable_or_broken_engine_is_an_engine_error_never_a_verdict(judge0, failure) -> None:
    engine, router = judge0
    route = router.post("/submissions")
    route.mock(side_effect=failure) if isinstance(failure, Exception) else route.mock(return_value=failure)
    with pytest.raises(EngineError):
        await engine.execute(_request())


async def test_a_language_without_an_engine_id_cannot_be_sent(judge0) -> None:
    engine, _ = judge0
    sql = LanguageSpec("sqlite", LanguageKind.SQL, None, "q.sql")
    with pytest.raises(EngineError, match="no Judge0 language id"):
        await engine.execute(ExecutionRequest(sql, "select 1", "", LIMITS))


async def test_the_engines_language_list_can_be_read(judge0) -> None:
    engine, router = judge0
    router.get("/languages").mock(return_value=httpx.Response(200, json=[{"id": 54, "name": "C++ (GCC 9.2.0)"}]))
    assert await engine.list_languages() == [{"id": 54, "name": "C++ (GCC 9.2.0)"}]
