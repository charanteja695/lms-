# Running Judge0 for this service

Production runs student code on a **self-hosted Judge0** (docs/PRODUCT.md decision D4). Judge0 does the isolation;
this service only talks to its HTTP API (`app/engines/judge0.py`). Anything below marked **verify** depends on the
Judge0 version you deploy: its configuration keys and language ids have changed between releases, and this file could
not be checked against a running Judge0 during development (there was no Docker on the development machine). Treat it
as the checklist of what this service *requires*, and confirm each item against the docs of your Judge0 version.

## What this service requires of Judge0

| Requirement | Why | Setting (verify) |
|---|---|---|
| Synchronous results | the engine calls `POST /submissions?wait=true` | `ENABLE_WAIT_RESULT=true` |
| Base64 payloads | source and output travel base64-encoded, so any byte survives | supported by default |
| Compiler options | `cpp17` and `cpp20` share one engine language and differ by `-std=` | `ENABLE_COMPILER_OPTIONS=true`, and list the C/C++ ids in `ALLOWED_LANGUAGES_FOR_COMPILER_OPTIONS` |
| Limits at least as high as ours | a request above the server maximum is refused | `MAX_CPU_TIME_LIMIT`, `MAX_WALL_TIME_LIMIT`, `MAX_MEMORY_LIMIT`, `MAX_FILE_SIZE` >= the largest limit a problem can ask for (`PROBLEM_MAX_TIME_LIMIT_MS` x the slowest language multiplier, `PROBLEM_MAX_MEMORY_MB` x 2 for JVM languages) |
| A shared secret | only this service's workers may submit | `AUTHN_HEADER=X-Auth-Token`, `AUTHN_TOKEN=<secret>`; set `JUDGE0_AUTH_TOKEN` to the same value |
| One run per submission | the engine sends `number_of_runs=1` | leave `MAX_NUMBER_OF_RUNS` >= 1 |

A ready-to-adapt `judge0.conf` is next to this file.

## Language ids

`runtimes/languages.json` carries an `engine_language_id` per language. The numbers shipped are Judge0 CE 1.13.1's;
its bundled compilers are **older** than the versions the platform targets (Java 21, Python 3.12, Node 22, ...). To run
the target versions, build custom language images in your Judge0 deployment and change the ids in the JSON to match, then:

```bash
python -m app.cli sync-languages      # load the catalogue into the database (run on every deploy)
python -m app.cli verify-languages    # ask the running Judge0 which language each id is, and fail on an id it does not have
```

`verify-languages` exits 1 if an id does not exist and prints what the engine calls each one. **Read the names**: an id
that exists but names the wrong language would run students' code in it silently.

## Hardening posture (the platform's promise, docs/PRODUCT.md §5.2)

Judge0 uses `isolate` (namespaces + cgroups). What to insist on when deploying it:

- **A fresh sandbox per execution.** Judge0 does this per submission; do not enable any "reuse" or warm-sandbox mode.
- **No network from student code.** Keep network access off for submissions (verify the key on your version, e.g.
  `ENABLE_NETWORK=false` / `ALLOW_ENABLE_NETWORK=false`); this service never asks for it.
- **Not reachable from anywhere but the workers.** Put Judge0 on a private network; only `code-execution-service`
  workers may call it. The API does not need to reach it at all.
- **Limits enforced by Judge0, not only requested:** CPU time, wall time, memory, stack, processes/threads, file size.
  This service sends them on every call; the server maximums are the ceiling if a bug ever sends too much.
- **Run Judge0's workers on their own hosts,** away from the database and Redis: a sandbox escape must not land next to
  anything valuable. `isolate` needs privileged containers and cgroups: this is the one component that cannot be
  hardened by unprivileged-container defaults.
- **cgroup version.** Older Judge0 needs cgroup v1; on a cgroup-v2 host follow your version's instructions.
- **Rotate `AUTHN_TOKEN`** like any secret, and keep it out of images.

## Sizing

The platform code is not the bottleneck: one worker process sustains a few hundred jobs a second of pure queue and
database work (`scripts/load_test.py`). Sandbox capacity is: budget for the *sandbox time* of your peak (docs/PRODUCT.md
§8: 3,000 runs/s at peak, exam-week) and scale Judge0 workers to that, then set `WORKER_CONCURRENCY` on each
`code-execution-service` worker to what the Judge0 pool behind it can absorb. The autoscaling signal is
`GET /api/v1/internal/queue`: scale on the depth of lane 2 (exam) first.
