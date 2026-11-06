"""Judge0 engine (docs/PRODUCT.md D4): a self-hosted Judge0 does the isolation (isolate/cgroups, no network,
non-root); this class only translates our request into its API and its status codes into ours.

Expected output is deliberately NOT sent to Judge0: we compare ourselves (app/utils/comparison.py) so every
compare mode works the same on every engine. Hardening of the Judge0 deployment itself is documented in
runtimes/judge0/README.md.
"""

import base64
import binascii
from typing import Any

import httpx

from app.core.config import Settings
from app.engines.base import EngineError, ExecutionRequest, ExecutionResult, Outcome

# Judge0 status ids (https://ce.judge0.com): 3 accepted (ran to completion), 4 wrong answer (unused: we send no
# expected output), 5 time limit, 6 compilation error, 7 SIGSEGV, 8 SIGXFSZ, 9 SIGFPE, 10 SIGABRT, 11 NZEC,
# 12 other runtime error, 13 internal error, 14 exec format error.
_RAN = {3, 4}
_TIME_LIMIT = 5
_COMPILATION = 6
_OUTPUT_LIMIT = 8  # SIGXFSZ: the program wrote past max_file_size
_RUNTIME = {7, 9, 10, 11, 12, 14}
_INTERNAL = 13
_MEMORY_HINT_RATIO = 0.95  # Judge0 has no memory-limit status: a crash near the limit is one


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return base64.b64decode(value).decode(errors="replace")
    except (binascii.Error, ValueError):
        return ""


class Judge0Engine:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        headers = {}
        if settings.JUDGE0_AUTH_TOKEN:
            headers["X-Auth-Token"] = settings.JUDGE0_AUTH_TOKEN.get_secret_value()
        self.client = client or httpx.AsyncClient(
            base_url=settings.JUDGE0_URL.rstrip("/"), headers=headers, timeout=settings.JUDGE0_TIMEOUT_SECONDS
        )

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if request.language.engine_language_id is None:
            raise EngineError(f"{request.language.code} has no Judge0 language id")
        limits = request.limits
        body: dict[str, Any] = {
            "language_id": request.language.engine_language_id,
            "source_code": base64.b64encode(request.source.encode()).decode(),
            "stdin": base64.b64encode(request.stdin.encode()).decode(),
            "cpu_time_limit": limits.cpu_time_s,
            "wall_time_limit": limits.wall_time_s,
            "memory_limit": limits.memory_mb * 1024,  # KB
            "max_file_size": max(limits.output_bytes // 1024, 1),  # KB
            "number_of_runs": 1,
            "enable_per_process_and_thread_time_limit": False,
            "enable_per_process_and_thread_memory_limit": False,
        }
        if request.language.compiler_options:
            body["compiler_options"] = request.language.compiler_options
        try:
            response = await self.client.post("/submissions", params={"base64_encoded": "true", "wait": "true"}, json=body)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise EngineError(f"Judge0 request failed: {exc}") from exc
        return self._translate(data, request)

    def _translate(self, data: dict[str, Any], request: ExecutionRequest) -> ExecutionResult:
        status_id = int((data.get("status") or {}).get("id", _INTERNAL))
        stdout, stderr = _decode(data.get("stdout")), _decode(data.get("stderr"))
        compile_output, message = _decode(data.get("compile_output")), _decode(data.get("message"))
        time_ms = int(float(data["time"]) * 1000) if data.get("time") not in (None, "") else None
        memory_kb = int(data["memory"]) if data.get("memory") is not None else None
        exit_code = data.get("exit_code")

        def result(outcome: Outcome) -> ExecutionResult:
            return ExecutionResult(
                outcome, stdout, stderr, compile_output, message, time_ms=time_ms, memory_kb=memory_kb, exit_code=exit_code
            )

        if status_id in _RAN:
            return result(Outcome.OK)
        if status_id == _TIME_LIMIT:
            return result(Outcome.TIME_LIMIT_EXCEEDED)
        if status_id == _COMPILATION:
            return result(Outcome.COMPILATION_ERROR)
        if status_id == _OUTPUT_LIMIT:
            return result(Outcome.OUTPUT_LIMIT_EXCEEDED)
        if status_id in _RUNTIME:
            limit_kb = request.limits.memory_mb * 1024
            if memory_kb is not None and memory_kb >= limit_kb * _MEMORY_HINT_RATIO:
                return result(Outcome.MEMORY_LIMIT_EXCEEDED)
            return result(Outcome.RUNTIME_ERROR)
        return result(Outcome.INTERNAL_ERROR)

    async def aclose(self) -> None:
        await self.client.aclose()

    async def list_languages(self) -> list[dict[str, Any]]:
        """The engine's own language list, to check our configured ids against it (``verify-languages``)."""
        try:
            response = await self.client.get("/languages")
            response.raise_for_status()
            return list(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise EngineError(f"Judge0 request failed: {exc}") from exc
