"""code-execution-service's internal API: run a candidate's code in the coding round, exactly as if they had pressed Run in the compiler."""

from dataclasses import dataclass

import httpx

from app.clients.errors import Rejected, Unavailable
from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class RunResult:
    run_id: int
    status: str  # queued | running | completed
    outcome: str | None
    stdout: str
    stderr: str
    compile_output: str
    time_ms: int | None


def _result(run: dict[str, object]) -> RunResult:
    return RunResult(
        run_id=int(str(run["run_id"])), status=str(run["status"]), outcome=str(run["outcome"]) if run.get("outcome") else None, stdout=str(run.get("stdout") or ""),
        stderr=str(run.get("stderr") or ""), compile_output=str(run.get("compile_output") or ""), time_ms=int(str(run["time_ms"])) if run.get("time_ms") is not None else None,
    )


class CodeExecutionClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.settings.CODE_EXECUTION_URL.rstrip("/"), timeout=self.settings.CODE_EXECUTION_TIMEOUT_SECONDS, transport=self._transport)

    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Service-Token": self.settings.INTERNAL_SERVICE_TOKEN.get_secret_value()}

    @staticmethod
    def _check(response: httpx.Response) -> None:
        if response.status_code in (408, 429) or response.status_code >= 500:
            raise Unavailable(f"code-execution-service answered {response.status_code}")
        if response.status_code >= 400:
            raise Rejected(f"code-execution-service answered {response.status_code}", status=response.status_code)

    async def run(self, *, user_id: int, organization_id: int | None, language: str, source: str, stdin: str = "", wait_seconds: float = 15.0) -> RunResult:
        """Queue a run and wait (up to ``wait_seconds``) for it to finish. A run that has not finished in time is returned as it stands."""
        body = {"user_id": str(user_id), "organization_id": str(organization_id) if organization_id else None, "language": language, "source": source, "stdin": stdin}
        try:
            async with self._client() as client:
                created = await client.post("/api/v1/internal/runs", json=body, headers=self._headers())
                self._check(created)
                run = created.json()["run"]
                result = await client.get(f"/api/v1/internal/runs/{run['run_id']}", params={"wait": wait_seconds}, headers=self._headers())
                self._check(result)
                return _result(result.json()["run"])
        except httpx.HTTPError as exc:
            raise Unavailable(f"code-execution-service unreachable: {exc.__class__.__name__}") from exc
