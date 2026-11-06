# Code Execution Service

> Status: **Done** · Roadmap phase: **4** · Local port: **8006** · Blueprint: [docs/PRODUCT.md](../../docs/PRODUCT.md) §5.2

The online compiler and the judge: run code on custom input, submit solutions to coding and SQL problems judged against
hidden test cases, and flag copied work.

| | |
|---|---|
| Owns (own database) | languages, problems, test_cases (encrypted), runs, submissions, submission_results, saved_codes, code_fingerprints, idempotency_keys, outbox_events |
| Emits events | `submission.judged` |
| Consumes events | none (problems are authored here) |

Follows the service template in [lms-backend/README.md](../README.md): verifies tokens against user-management's JWKS
(never issues its own), checks the shared Redis access-state for revocation, transactional outbox to `lms:events`.

## What it does

- **Languages by configuration.** The 15 blueprint languages plus C++17/20 and TypeScript, and SQL (SQLite and
  PostgreSQL dialects), are rows in `languages`, loaded from [runtimes/languages.json](runtimes/languages.json). Adding
  one is a JSON entry plus a runtime on the engine, no code. Each carries its file name, editor mode, starter template,
  compiler options and time/memory multipliers (Python and Java get more time and memory than C, so no language is
  penalised).
- **Runs** with custom input: queued, executed by a worker, read back by polling, `?wait=` long-poll, or a server-sent
  event stream.
- **Submissions** judged against every test case with per-case verdicts (`accepted`, `wrong_answer`,
  `time_limit_exceeded`, `memory_limit_exceeded`, `runtime_error`, `compilation_error`, `output_limit_exceeded`,
  `internal_error`), a weighted score, and a `submission.judged` event for assessment-service.
- **Problems** authored by content authors: draft, publish (freezes it), retire. Coding problems judge stdin/stdout;
  SQL problems judge a query's result set against hidden datasets.
- **Hidden test cases** are encrypted at rest and never sent to a client. Samples are shown; for a hidden case a
  student sees the verdict only, never its input, expected output or an error message that could quote them.
- **Exam lane.** Submissions made through the internal endpoint by assessment-service go in the exam lane and are served
  ahead of all practice work however late they arrive.
- **Per-user and per-institution rate limits**, `Idempotency-Key` on every create, per-problem/per-language saved code.
- **Plagiarism signal.** Every submission is fingerprinted (winnowing over a normalised token stream) and compared with
  other people's submissions to the same problem; renamed variables, changed literals and comments do not hide a copy.
  Reviewers get a flag, the percentage and the matched submission. It is a signal for a human, never a decision.

## Architecture

```
POST /runs, POST /problems/{id}/submissions          assessment-service: POST /internal/submissions (exam lane)
        │  (a row in `runs` / `submissions`: the queue)                    │
        ▼                                                                   ▼
   claim with SKIP LOCKED + a lease, lanes served 2 (exam) > 1 (submission) > 0 (run)
        │
   worker: 1. read (short DB session)  2. execute, holding NO connection  3. record (short DB session)
        │                                   │
        │                        ExecutionEngine ── Judge0 (production)   ── local subprocess (dev/test only)
        │                                   └────── SQLite / PostgreSQL SQL engines (own sandboxes)
        ▼
   result on the row  ─►  outbox  ─►  lms:events (`submission.judged`)
```

Design notes worth knowing:

- **The engine is an interface** (`app/engines/base.py`). Nothing above it knows about Judge0; expected output is never
  sent to an engine, so every compare mode (`exact`, `trim`, `token`, `float`, `rows_ordered`, `rows_unordered`) works
  identically on all of them.
- **A database queue with leases**, not a broker: jobs are rows, workers `SELECT ... FOR UPDATE SKIP LOCKED` and push
  `available_at` out by a lease. A worker that dies mid-job just lets the lease lapse; nothing is lost and nothing stays
  locked while code runs. After `JOB_MAX_ATTEMPTS` a job is given up as `internal_error`. An *engine* failure (Judge0
  down) is retried with backoff and never becomes a student's verdict; only a *program* failure is a verdict.
- **No DB connection is held while code runs.** Each job reads, releases the connection, executes, then records in a new
  short session. Holding one per in-flight execution exhausted the pool (measured below). A worker sizes its own pool to
  `WORKER_CONCURRENCY` (`Settings.worker_db_pool_size`).
- **Continuous claiming.** One claimer keeps a worker's execution slots full as they free up, instead of waiting for the
  slowest job of a batch (a 10 s run among 100 ms ones would idle every other slot).
- **A compile error is compiled once,** not once per test case; each case still gets its own row.
- **SQL problems.** A problem has a setup script (schema and seed data, encrypted) and each test case's `input` is *extra
  seed data* run after it, so hidden cases test different datasets and a hard-coded answer cannot pass. The student's query
  is one statement; SQLite runs in an in-memory database behind an authorizer (no ATTACH/PRAGMA/file functions) with a
  progress-handler deadline; PostgreSQL runs in a transaction that is always rolled back with `search_path = pg_temp`,
  against a dedicated low-privilege sandbox cluster ([runtimes/sql/postgres_sandbox.sql](runtimes/sql/postgres_sandbox.sql)).
- **Encryption** is Fernet with several keys (newest first) so a key can be rotated: `python -m app.cli rotate-keys`.

## API (`/api/v1`)

Full schema: [docs/openapi.json](docs/openapi.json) (import into Postman) and `/docs` when running.

| Endpoint | Who |
|---|---|
| `GET /languages` | any signed-in user (what the editor needs to switch language) |
| `GET /languages/all`, `POST /languages`, `PATCH /languages/{code}` | `super_admin` |
| `POST /runs`, `GET /runs/{id}` (`wait`), `GET /runs/{id}/stream` (SSE) | any signed-in user; own runs only |
| `GET /problems` (filters, `solved`), `GET /problems/{id}` | any signed-in user; students see published only |
| `PUT/GET /problems/{id}/code/{language}` | any signed-in user; own saved code (starter template if none) |
| `POST /problems/{id}/submissions`, `GET /submissions`, `GET /submissions/{id}` (`wait`) | any signed-in user; own only |
| `POST/PATCH/DELETE /problems`, `.../publish`, `.../retire`, `.../test-cases` (+`/bulk`, `/reorder`) | `content.author` or `super_admin` |
| `GET /problems/{id}/author`, `.../test-cases`, `.../stats`, `GET /review/submissions[/{id}[/similar]]` | reviewers: `content.author`, `content.review`, `exams.manage`, `super_admin` |
| `POST /internal/submissions`, `GET /internal/submissions/{id}`, `GET /internal/queue` | assessment-service, with `X-Internal-Service-Token` |
| `POST /internal/runs`, `GET /internal/runs/{id}` (`wait`) | ai-interview-service, with `X-Internal-Service-Token` — a candidate's coding-round code, run exactly as `POST /runs` would |

Another user's run or submission looks exactly like a missing one (404).

## Local development

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
python scripts/generate_env_example.py && cp .env.example .env
alembic upgrade head
python -m app.cli sync-languages
uvicorn app.main:app --reload --port 8006     # http://localhost:8006/docs
python -m app.worker                           # outbox relay, run + submission workers, housekeeping
pytest
```

`EXECUTION_ENGINE=local` (the default) runs Python, JavaScript and Bash as **plain subprocesses with no isolation**; it
exists so the pipeline can be exercised without Judge0 and Settings refuses to start staging/production with it. Set
`EXECUTION_ENGINE=judge0` with `JUDGE0_URL` / `JUDGE0_AUTH_TOKEN` there, and follow
[runtimes/judge0/README.md](runtimes/judge0/README.md). Set `TEST_CASE_ENCRYPTION_KEYS` (generate with
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) and
`INTERNAL_SERVICE_TOKEN`; staging/production refuse the development values.

Operating it: scale workers on `GET /internal/queue` (depth per lane, scale on lane 2 first); `WORKER_CONCURRENCY` is
executions in flight per worker process; `python -m app.cli verify-languages` after every Judge0 change; finished runs are
pruned after `RUNS_RETENTION_DAYS`, submissions are never deleted.

## Tests

211 tests (`tests/unit`, `tests/integration`), ruff-clean. mypy reports only the accepted alias-factory gap
(`text()`/`id_field()` types), as in every service. They cover:

- comparison in every mode, fingerprint stability under renaming, encryption and key rotation, production-config refusals;
- **real execution**: the local engine running real Python (stdin, crashes, time limits, output floods, minimal environment)
  and the whole judging pipeline on real programs (accepted, wrong answer, runtime error, time limit, weighted score,
  hidden cases never leaking, per-case data, first-failing-case verdict);
- **real databases**: the SQLite engine (result format, injections, runaway queries) and the PostgreSQL SQL engine on a real
  PostgreSQL 16 with the documented sandbox role applied as written (no file/server access, nothing persists, concurrent
  runs invisible to each other);
- the Judge0 engine against a mocked Judge0 API (request shape, status mapping, outages become engine errors);
- the queue on a real PostgreSQL: three concurrent workers claiming 60 jobs with no overlap and none missed, the
  migration applied, reversed and re-applied with no drift, six simultaneous requests sharing one idempotency key making one
  submission, the worker loop's drain, concurrency bound and resilience to a crashing job;
- authorization for every endpoint group, tenancy of runs and submissions, the exam lane's ordering, rate limits per user
  and per institution, idempotent retries (including the unique-constraint race, forced deterministically), long-poll and SSE,
  and API-wide contract checks (every success envelope keeps `code: SUCCESS`).

## Load check

`python scripts/load_test.py` (embedded PostgreSQL, simulated 20 ms engine). On the development machine, one process:

| | Result |
|---|---|
| Enqueue via `POST /runs` (64 concurrent) | ~320 req/s, p50 187 ms, p99 249 ms |
| Drain (2 worker loops x 32 in flight) | ~370 jobs/s |
| Exam submission behind 500 queued practice submissions | judged in ~250 ms; 31 of the 500 practice jobs were done by then |

The load check found two real problems that are fixed: holding a DB connection through execution, and a lock-step batch
loop. With the connection held and a default-sized pool the same drain ran at ~35 jobs/s. These numbers are the
**platform overhead** (queue, database, ORM) on one machine and one CPU core. They are not sandbox capacity: that is
Judge0's, and it is the limit (see "Sizing" in [runtimes/judge0/README.md](runtimes/judge0/README.md)).

## Not built / not verified

**Not built**

- **MySQL dialect.** The dialect registry takes another engine, but safe per-run isolation on MySQL needs a per-run account
  design that could not be tested without a MySQL server. PostgreSQL and SQLite are done.
- **Custom checkers and interactive problems** (output judged by a program rather than compared).
- **Institution heads reading their students' submissions** (only the student and platform reviewers can today).
- **Push over WebSocket.** Results are available by polling, long-poll and server-sent events.

**Written but not exercised** (nothing on the development machine could run them; each is tested against the closest thing
available and named here so no one assumes more)

- **Judge0 itself and every language except Python, JavaScript and Bash.** No Docker, JDK or compilers were available. The
  engine is verified against a mocked Judge0 API; the language ids in `languages.json` are Judge0 CE 1.13.1's and must be
  checked with `python -m app.cli verify-languages` against the deployment, which needs custom images for the target
  versions (Java 21, Python 3.12, Node 22). The hardening settings in `runtimes/judge0/` are guidance to verify.
- **Memory-limit and network isolation of the sandbox.** The local engine has neither; the SQLite/PostgreSQL engines were
  tested for what they do, but real cgroup/namespace containment is Judge0's job and was not run.
- **A load test against real Judge0**, and any multi-machine scaling.

**Known limits.** The queue is a database table: at sustained thousands of jobs a second the claim step is what to move to
a stream, without touching the judge. Each test case is its own Judge0 call, so a compiled language is compiled again for every case
(Judge0's batch endpoint could compile once). The internal token is one shared secret, not a per-service
identity (same caveat as subscription-service). Plagiarism compares by token structure across all languages; it does not
understand a language's semantics.
