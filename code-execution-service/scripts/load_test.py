"""Load check of this service's hot path (docs/PRODUCT.md §9: "load check on its hot path").

    python scripts/load_test.py                        # embedded PostgreSQL (pgserver), simulated engine
    python scripts/load_test.py --database-url postgresql+asyncpg://...  --runs 20000 --workers 4 --concurrency 64
    python scripts/load_test.py --real-engine          # also push a few runs through the local subprocess engine

What it measures, and what it does NOT:
  * enqueue    how fast the API accepts runs (auth, validation, rate-limit bypass, one INSERT), end to end;
  * drain      how fast workers claim, execute (a simulated engine with a fixed latency) and record results,
               i.e. the queue and database path. With an engine that takes L ms and W executions in flight, the
               ceiling is about W / L jobs a second: that is the number to size the worker pool from;
  * exam lane  whether an exam submission arriving behind a backlog of practice work is served first.
It does NOT measure sandbox capacity (Judge0 / real compilers) and uses one machine, so absolute numbers are a
floor for the platform code, not a capacity plan.
"""

import argparse
import asyncio
import os
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import fakeredis.aioredis
from httpx import ASGITransport, AsyncClient
from lms_common.auth import AccessTokenClaims
from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.api.deps import _authenticate  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.core.crypto import SecretCipher  # noqa: E402
from app.db.session import build_engine, build_sessionmaker  # noqa: E402
from app.domain.enums import JobStatus  # noqa: E402
from app.engines.base import ExecutionRequest, ExecutionResult, Outcome  # noqa: E402
from app.engines.factory import build_engine as build_execution_engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.run import Run  # noqa: E402
from app.models.submission import Submission  # noqa: E402
from app.services.judge_service import JudgeService  # noqa: E402
from app.services.language_service import LanguageService  # noqa: E402
from app.worker.runner import run_job_loop  # noqa: E402

V1 = "/api/v1"


def claims(user_id: int, role: str = "student", scopes: tuple[str, ...] = ()) -> AccessTokenClaims:
    now = datetime.now(UTC)
    return AccessTokenClaims(user_id=user_id, session_id=1, role=role, organization_id=1755000000000001, organization_type="institution",
                             scopes=scopes, token_version=0, token_id="load", issued_at=int(now.timestamp()), expires_at=now)  # noqa: S106


class SimulatedEngine:
    """An engine that takes a fixed time per execution, like a Judge0 round trip, and always says the program printed 3."""

    def __init__(self, latency_ms: float) -> None:
        self.latency = latency_ms / 1000

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        await asyncio.sleep(self.latency)
        return ExecutionResult(Outcome.OK, stdout="3\n", time_ms=int(self.latency * 1000))


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(int(len(ordered) * p), len(ordered) - 1)]


async def timed_posts(client: AsyncClient, count: int, concurrency: int, make_request, expect: int = 202) -> tuple[float, list[float]]:
    gate, latencies = asyncio.Semaphore(concurrency), []

    async def one(n: int) -> None:
        async with gate:
            started = time.perf_counter()
            response = await make_request(client, n)
            assert response.status_code == expect, response.text
            latencies.append((time.perf_counter() - started) * 1000)

    started = time.perf_counter()
    await asyncio.gather(*(one(n) for n in range(count)))
    return time.perf_counter() - started, latencies


async def wait_until_done(sessionmaker, model, expected: int, limit_seconds: float = 600) -> float:
    started = time.perf_counter()
    while time.perf_counter() - started < limit_seconds:
        async with sessionmaker() as db:
            done = (await db.execute(select(func.count()).select_from(model).where(model.status == JobStatus.COMPLETED))).scalar_one()
        if done >= expected:
            return time.perf_counter() - started
        await asyncio.sleep(0.05)
    raise TimeoutError(f"{model.__name__}: not all {expected} jobs finished in {limit_seconds}s")


async def start_workers(sessionmaker, settings, engine, model, process, workers: int, stop: asyncio.Event):
    slots = asyncio.Semaphore(settings.WORKER_CONCURRENCY)
    return [asyncio.create_task(run_job_loop(model.__name__, model, process, sessionmaker, settings, slots, stop)) for _ in range(workers)]


async def run(args: argparse.Namespace) -> None:
    pg = None
    url = args.database_url
    if url is None:
        import pgserver

        pg = pgserver.get_server(tempfile.mkdtemp(prefix="ce_load_"), cleanup_mode="delete")
        pg.psql("CREATE DATABASE lms_code_execution;")
        url = pg.get_uri().rsplit("/", 1)[0].replace("postgresql://", "postgresql+asyncpg://", 1) + "/lms_code_execution"
    upgrade = await asyncio.to_thread(
        subprocess.run, [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT,
        env={**os.environ, "DATABASE_URL": url}, capture_output=True, text=True, check=False,
    )
    if upgrade.returncode:
        raise SystemExit(upgrade.stderr[-1500:])

    settings = Settings(ENVIRONMENT="test", DATABASE_URL=url, LOG_LEVEL="ERROR", LOG_JSON=False, RATE_LIMIT_ENABLED=False,
                        WORKER_CONCURRENCY=args.concurrency, JOB_BATCH_SIZE=min(args.concurrency, 200), WORKER_POLL_SECONDS=0.02,
                        DB_POOL_SIZE=args.pool_size or args.workers * (args.concurrency + 6), DB_MAX_OVERFLOW=10)
    engine = build_engine(settings)
    sessionmaker = build_sessionmaker(engine)
    async with sessionmaker() as db:
        await LanguageService(db).sync_from_file(ROOT / "runtimes" / "languages.json")

    app = create_app(settings)
    app.state.engine, app.state.sessionmaker = engine, sessionmaker
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_settings] = lambda: settings
    who = {"claims": claims(1755000000000101, role="admin", scopes=("content.author",))}
    app.dependency_overrides[_authenticate] = lambda: who["claims"]

    cipher = SecretCipher.from_settings(settings)
    judge = JudgeService(sessionmaker, SimulatedEngine(args.engine_latency_ms), settings, cipher)
    print(f"database: {'embedded PostgreSQL' if pg else url.split('@')[-1]}   workers: {args.workers}   in flight per worker: "
          f"{args.concurrency}   simulated engine latency: {args.engine_latency_ms} ms\n")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # ---------------------------------------------------------------- enqueue
        who["claims"] = claims(1755000000000201)
        await timed_posts(client, 400, args.http_concurrency, lambda c, n: c.get(f"{V1}/languages"), expect=200)  # warm the pool
        elapsed, latencies = await timed_posts(
            client, args.runs, args.http_concurrency,
            lambda c, n: c.post(f"{V1}/runs", json={"language": "python3", "source": f"print({n})"}),
        )
        print(f"enqueue   {args.runs} runs via POST /runs           {args.runs / elapsed:8.0f} req/s   "
              f"p50 {statistics.median(latencies):6.1f} ms   p95 {percentile(latencies, .95):6.1f} ms   p99 {percentile(latencies, .99):6.1f} ms")

        # ---------------------------------------------------------------- drain
        stop = asyncio.Event()
        tasks = await start_workers(sessionmaker, settings, None, Run, judge.process_run, args.workers, stop)
        drained = await wait_until_done(sessionmaker, Run, args.runs)
        print(f"drain     {args.runs} runs, {args.workers} worker(s)          {args.runs / drained:8.0f} jobs/s   "
              f"(ceiling for this engine latency ~ {args.workers * args.concurrency / (args.engine_latency_ms / 1000):.0f} jobs/s)")
        stop.set()
        await asyncio.gather(*tasks)

        # ---------------------------------------------------------------- exam lane
        who["claims"] = claims(1755000000000101, role="admin", scopes=("content.author",))
        created = await client.post(f"{V1}/problems", json={"title": "Load test problem", "statement": "x"})
        problem_id = created.json()["problem"]["problem_id"]
        await client.post(f"{V1}/problems/{problem_id}/test-cases", json={"input": "1 2", "expected": "3"})
        await client.post(f"{V1}/problems/{problem_id}/publish")

        practice = args.backlog
        who["claims"] = claims(1755000000000301)
        await timed_posts(client, practice, args.http_concurrency,
                          lambda c, n: c.post(f"{V1}/problems/{problem_id}/submissions", json={"language": "python3", "source": f"print({n})"}))
        exam = await client.post(f"{V1}/internal/submissions", headers={"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN.get_secret_value()},
                                 json={"user_id": "1755000000000401", "problem_id": problem_id, "language": "python3", "source": "print(3)", "reference": "attempt:load"})
        assert exam.status_code == 202, exam.text
        exam_public_id = int(exam.json()["submission"]["submission_id"])

        stop = asyncio.Event()
        started = time.perf_counter()
        tasks = await start_workers(sessionmaker, settings, None, Submission, judge.process_submission, args.workers, stop)
        exam_done = None
        while exam_done is None:
            async with sessionmaker() as db:
                row = (await db.execute(select(Submission.status).where(Submission.public_id == exam_public_id))).scalar_one()
            if row == JobStatus.COMPLETED:
                exam_done = time.perf_counter() - started
            await asyncio.sleep(0.01)
        async with sessionmaker() as db:
            finished_by_then = (await db.execute(select(func.count()).select_from(Submission).where(
                Submission.status == JobStatus.COMPLETED, Submission.public_id != exam_public_id))).scalar_one()
        total = await wait_until_done(sessionmaker, Submission, practice + 1)
        print(f"exam lane 1 exam submission behind {practice} practice   judged after {exam_done * 1000:7.0f} ms; only {finished_by_then} of "
              f"{practice} practice submissions were done by then (all {practice + 1} took {total:.1f} s)")
        stop.set()
        await asyncio.gather(*tasks)

        # ---------------------------------------------------------------- real engine (optional)
        if args.real_engine:
            real = JudgeService(sessionmaker, build_execution_engine(settings.model_copy(update={"EXECUTION_ENGINE": "local"})), settings, cipher)
            who["claims"] = claims(1755000000000501)
            count = args.real_runs
            await timed_posts(client, count, args.http_concurrency, lambda c, n: c.post(f"{V1}/runs", json={"language": "python3", "source": f"print({n} * 2)"}))
            async with sessionmaker() as db:
                before = (await db.execute(select(func.count()).select_from(Run).where(Run.status == JobStatus.COMPLETED))).scalar_one()
            stop = asyncio.Event()
            tasks = await start_workers(sessionmaker, settings, None, Run, real.process_run, args.workers, stop)
            took = await wait_until_done(sessionmaker, Run, before + count)
            print(f"real engine {count} python runs as real subprocesses    {count / took:8.1f} jobs/s  (process start-up dominates; not a sandbox figure)")
            stop.set()
            await asyncio.gather(*tasks)

    await engine.dispose()
    if pg is not None:
        pg.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database-url", help="postgresql+asyncpg://... (default: an embedded PostgreSQL via pgserver)")
    parser.add_argument("--runs", type=int, default=2_000)
    parser.add_argument("--backlog", type=int, default=400, help="practice submissions queued ahead of the exam submission")
    parser.add_argument("--workers", type=int, default=2, help="worker loops (each stands in for a worker process)")
    parser.add_argument("--concurrency", type=int, default=32, help="executions in flight per worker (WORKER_CONCURRENCY)")
    parser.add_argument("--http-concurrency", type=int, default=64)
    parser.add_argument("--pool-size", type=int, default=None, help="DB_POOL_SIZE; default: what real workers would use, per worker")
    parser.add_argument("--engine-latency-ms", type=float, default=20.0)
    parser.add_argument("--real-engine", action="store_true")
    parser.add_argument("--real-runs", type=int, default=30)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
