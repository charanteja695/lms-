# Assessment Service

> Status: **Done** · Roadmap phase: **5** · Local port: **8007** · Blueprint: [docs/PRODUCT.md](../../docs/PRODUCT.md) §5.1

The question bank and everything around taking a test: topic, module and proctored final tests, practice tests and an
employer's hiring assessments. Randomised per-student papers, autosaved answers with a server-authoritative timer,
grading (automatic, by code-execution-service, or by a person), results, integrity-aware pass/fail and `course.passed`.

| | |
|---|---|
| Owns (own database) | questions, question_versions, question_version_tags, question_stats, tests, test_sections, section_slots, test_schedules, test_assignments, attempts, attempt_questions, attempt_sections, attempt_answers, attempt_events, coding_submissions, enrollment_refs, version_refs, version_targets, idempotency_keys, processed_events, outbox_events |
| Emits events | `test.published`, `test.retired`, `attempt.started`, `attempt.submitted`, `attempt.graded`, `attempt.finalized`, `course.passed`, `course.failed`, `course.pass_revoked` |
| Consumes events | `enrollment.created/removed`, `course.eligible_for_final` (learning-service) · `course.published/retired` (catalog-service) · `submission.judged` (code-execution-service) · `integrity.flagged/decided` (proctoring-service) |
| Calls | code-execution-service `POST /internal/submissions` (exam lane) and `GET /internal/submissions/{id}`; S3 for file answers |
| API | [docs/API.md](docs/API.md) · [docs/openapi.json](docs/openapi.json) (63 operations; import into Postman) |

Follows the service template in [lms-backend/README.md](../README.md): verifies tokens against user-management's JWKS
(never issues its own), checks the shared Redis access-state for revocation, transactional outbox to `lms:events`,
idempotent consumers (`processed_events`), `Idempotency-Key` on creates and imports.

## What it does

- **Question bank** (§5.1). Ten question types — single/multi MCQ, true/false, fill-in (case-insensitive, numeric
  tolerance), match, ordering, coding, SQL, subjective (rubric) and file/project submission. Each carries difficulty
  1–5, Bloom level and skill/topic/tag tags. Questions are **versioned**: editing a published question opens a new draft,
  the live version keeps serving until a reviewer (`content.review`, not the author) approves it. Bulk import, filters,
  retire/restore.
- **Tests.** Sections of *fixed* questions and *pools* (N questions per student drawn by tags/difficulty/Bloom/type),
  overall or per-section time limits, negative marking, shuffled questions/options, attempt limit + cooldown, highest/
  latest score counting, result visibility (`immediate` / `after_window` / `manual`), review policy, proctoring level
  (`none`/`basic`/`strict`). Draft → in review → published (frozen; totals fixed) → retired. `GET /tests/{id}/validation`
  says what blocks publishing (pool too small, missing timing, unavailable questions).
- **Per-student papers.** Generated once as a pure function of a seed (auditable), **pinned to the exact question
  versions served**, cached in Redis. Match and ordering items are always shuffled; an ordering question never starts
  in the answer's order.
- **Attempts** (`not_started → in_progress ⇄ paused → submitted → grading → graded`). Preparing a paper does not use an
  attempt or start the clock; a student has at most one live attempt per test (enforced by a partial unique index).
  Resume after a refresh or crash is allowed and every resume is logged. Staff and the proctor can pause (the stopped
  time is given back), unpause and terminate.
- **Server-authoritative timer.** The deadline is fixed at start; every read and write re-checks it, a small network
  grace is allowed, and a worker sweep submits attempts nobody is touching. Per-section tests run each section on its own
  clock, in order; a finished section cannot be reopened.
- **Exam windows and the waiting room.** A scheduled exam (`exams.manage`) lets students *prepare* their paper from
  `WAITING_ROOM_LEAD_MINUTES` before it opens; starts are then admitted at most `WAITING_ROOM_ADMIT_PER_SECOND` per test
  per second (429 `WAITING_ROOM` + `Retry-After` with jitter), and a late starter is cut off at the window's end.
- **Answers go to Redis first** and are flushed to the database in batches (a per-answer `revision` means an out-of-order
  request never overwrites a newer answer). If Redis is unavailable the answer is written straight to the database.
- **Grading.** Objective answers are scored in-process (partial credit modes, negative marking that never takes a score
  below zero). Coding/SQL answers are queued to code-execution-service's **exam lane** through a durable
  `coding_submissions` row: dispatch is idempotent and retried with backoff, the verdict arrives as `submission.judged`
  *or* is polled if the event was missed, and an answer that cannot be judged (rejected, or no verdict in 30 min) goes to
  a person rather than leaving the attempt hanging. Subjective and file answers are graded by rubric or marks by staff of
  the student's institution, exam managers, or the owning employer; an exam manager may override an automatic grade
  (feedback required, audited). Regrade keeps human grades.
- **Results.** Pass = score ≥ pass mark **and** integrity `not_required`/`clear`/`reviewed_ok`. A failing score fails at
  once; a passing score on a proctored test waits for `integrity.decided`; `invalidated` always wins. A decided result
  becomes official when *released* (immediately / when the exam window closes / when staff release it) — that is what the
  student sees and what the platform hears (`attempt.finalized`, and for a final test `course.passed`, `course.failed`
  once attempts are exhausted, `course.pass_revoked` if an integrity case later invalidates a pass). A changed outcome
  after release is announced again with a higher `revision`.
- **Hiring assessments.** An employer authors its own questions and tests (its members write, its admin approves) and
  job-portal-service invites candidates (`POST /internal/assignments`); only the employer and the candidate see those
  attempts, not the candidate's institution.
- **Reports.** Results list (scoped by role: student → own, exam manager → all, institution staff → their students,
  employer → their hiring tests), CSV export streamed in pages, analytics (pass rate, score distribution, time), a
  plagiarism report from code-execution's similarity flags, and per-question **difficulty index** and **discrimination**
  computed from real attempts.

## Architecture

```
student ─ PUT /attempts/{id}/answers/{q} ─►  gate (Redis meta) ─► validate (Redis paper) ─► Redis hash + dirty set
                                                                                              │  worker: flush in batches
POST .../submit ─► attempt = `submitted` (a queue row) ───────────────────────────────────────▼
                                                                                        PostgreSQL
   worker: claim (SKIP LOCKED + lease) ─► grade objective ─► queue coding ──► code-execution-service (exam lane)
                 ▲                                              │                       │
   verdict event / poll / a person's grade ─────────────────────┘◄── submission.judged ──┘
                 ▼
   last outstanding grade ─► graded ─► result rules (+ integrity) ─► release ─► outbox ─► lms:events
```

- **Worker** (`python -m app.worker`, scale by running more): outbox relay, inbound consumer, answer flush, timeout
  sweep, grading, code dispatch, code reconcile, result release, statistics, housekeeping. Rows are claimed with
  `FOR UPDATE SKIP LOCKED` and a lease; buffered attempts are claimed atomically in Redis (`ZREM`).
- **Nothing calls another service for data it can get from events.** Whether a student may take a test comes from local
  read-models built from `enrollment.*`, `course.eligible_for_final` and catalog's `course.published` tree. A test is open
  to a student enrolled in a version that contains its topic/module **or lists that very test** (a cloned course version
  has new topic ids but keeps its predecessor's test).
- **Locks that actually lock.** Every locked read (`FOR UPDATE`) uses `populate_existing`, otherwise an ORM object loaded
  earlier in the request would be checked in its stale state (found by the PostgreSQL concurrency tests).

## Event contracts

Emitted (all ids are strings; every attempt event carries `attempt_id`, `test_id`, `test_kind`, `target_type/target_id`,
`user_id`, `organization_id`, `enrollment_id`, `version_id`, `course_id`, `attempt_no`, `proctoring_level`):

| Event | When | Adds |
|---|---|---|
| `test.published` / `test.retired` | a test is approved / retired | `title`, `kind`, `pass_mark_percent`, `max_attempts`, `cooldown_hours`, `duration_minutes`, `proctoring_level`, `total_marks`, `question_count` (catalog attaches `target_type` module/topic tests to its rows) |
| `attempt.started` | the clock starts | `started_at`, `deadline_at` — proctoring-service opens its session from this |
| `attempt.submitted` | manual, timeout or terminated | `submitted_at`, `submit_reason` |
| `attempt.graded` | every answer has a grade (score known, result may still be pending integrity) | `score`, `max_score`, `percent`, `pass_mark_percent`, `plagiarism_flagged` |
| `attempt.finalized` | the result is released — **learning-service should complete topic/module tests from this** | `result` (passed/failed/invalidated), `previous_result`, `score`, `percent`, `integrity_status`, `revision`, `released_at` |
| `course.passed` | a final test passed and released — certificate-service, career-service | `course_id`, `version_id`, `enrollment_id`, `student_user_id`, `percent`, `best_percent`, `pass_mark_percent`, `passed_at` |
| `course.failed` | a final test's attempts are exhausted without a pass | `attempts_used`, `percent`, `best_percent` |
| `course.pass_revoked` | an integrity case invalidated an earlier pass — certificate-service revokes | `reason`, `revoked_at` |

Consumed (payload contract for the producers):

| Event | Payload keys used |
|---|---|
| `enrollment.created` | `enrollment_id`, `student_user_id`, `organization_id`, `version_id` |
| `enrollment.removed` | `enrollment_id`, `student_user_id`, `version_id` |
| `course.eligible_for_final` | `enrollment_id`, `student_user_id`, `version_id` |
| `course.published` | `course_id`, `version_id`, `final_test_id`, `modules[].{module_id, module_test_id, topics[].{topic_id, topic_test_id}}` |
| `course.retired` | `version_id` |
| `submission.judged` | `reference` (`attempt:<attempt id>:<question id>`), `submission_id`, `verdict`, `passed`, `total`, `score`, `flagged`, `similarity_percent`, `similar_to_submission_id` |
| `integrity.flagged` | `attempt_id`, `status` (`flagged` \| `under_review`) |
| `integrity.decided` | `attempt_id`, `decision` (`clear` \| `reviewed_ok` \| `invalidated`) — a human confirms every invalidation, in proctoring-service |

learning-service consumes `attempt.finalized` (topic and module tests) to complete topics/modules — items done **and**
test passed — and to emit `topic.completed`, `module.completed` and `course.eligible_for_final` (which this service in
turn uses to open the final test).

Integration touches in other services made with this one: catalog-service's `test.published` handler now attaches only
`module`/`topic` targets (it used to treat any other target as a topic id); code-execution-service's `submission.judged`
gained `similar_to_submission_id` (additive, with a test).

## Run

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements-dev.txt
cp .env.example .env                         # generated by scripts/generate_env_example.py
alembic upgrade head
uvicorn app.main:app --port 8007             # API   (http://localhost:8007/docs)
python -m app.worker                         # worker (needs Redis; run more than one to scale)
pytest -m "not postgres"                     # 140 tests on SQLite + fakeredis + moto
pytest -m postgres                           # 7 tests on a real embedded PostgreSQL (pip install pgserver)
python scripts/load_test.py --students 300 --questions 30     # hot-path load check
```

Settings live in `app/core/config.py`; staging/production refuse to start on development defaults
(`INTERNAL_SERVICE_TOKEN`, S3 bucket, https JWKS, explicit hosts).

## Verification (2026-09-21)

- **147 tests** — 45 unit (graders, content/answer validation, timer clock, statistics), 95 integration on SQLite, and
  7 on a **real PostgreSQL** (`pgserver`): the migration is applied up → down → up and `alembic check` finds no drift
  from the models; concurrent prepares end in one attempt, concurrent submits emit one event, concurrent graders never
  claim the same attempt, concurrent grading of one attempt yields one result, concurrent dispatchers send each coding
  answer once. ruff and **mypy --strict clean** (0 issues).
- **Load check** (one process, PostgreSQL, *fake* Redis, 300 students × 30 questions, 50 concurrent): saving an answer
  p50 0.6 ms / p99 0.9 ms; flushing ~6,900 answers/s; grading ~96 attempts/s (~2,900 answers/s); prepare p50 283 ms and
  start p50 167 ms *under 50-way contention in one process*. These are this service's own overhead only — a real Redis
  adds a network round trip per save, so size from a run against one (see Scaling).

### Not built / not verified

- **Not exercised on this machine:** a real Redis server (fakeredis only), real S3 (moto), and code-execution-service
  itself (its HTTP API is mocked to the documented contract). A fakeredis-based test does not prove Redis persistence
  (AOF) settings, cluster behaviour or eviction; the answer buffer's durability rests on `appendonly yes` plus the 2 s
  flush interval, which bounds — but does not eliminate — what a Redis crash could lose.
- **proctoring-service now exists** (phase 6) and this service is built against its real contract, but the two have
  only been tested together through stand-ins (each side's tests mock the other's documented API). A proctored test's passing
  attempt waits for `integrity.decided`; nothing decides it automatically (proctoring clears low risk itself, a person decides
  the rest). Starting a proctored test needs proctoring-service's pre-check flag in Redis (`PROCTORING_PRECHECK_REQUIRED`); if
  Redis cannot be read the start is allowed, so an outage does not lock students out.
- **AI-assisted rubric grading** is not built: it needs ai-gateway (phase 7). The grade model already records who graded.
- **Text similarity for subjective answers** is not built (only code answers are compared, by code-execution).
- **Unlock gating.** A topic/module test requires enrolment and course membership, but not that the topic's videos and
  practice are done: that needs an "items done" signal from learning-service that does not exist yet.
- **A consumed event that raises is retried, then dead-lettered.** The shared `StreamConsumer` reclaims unacked events after
  60 s and moves one that fails 10 times to `lms:events:dead`, so a transient outage recovers by itself; a permanently
  failing event needs a person to look at that stream. Verdicts are additionally covered by the reconcile poll and
  `POST /internal/attempts/{id}/integrity` is the synchronous fallback for integrity decisions.
- No live push (WebSocket/SSE) of results or grading progress: clients poll `GET /attempts/{id}/result`.
- Question text is markdown only; images/attachments through media-service are not wired.
- Retiring a *published* question is refused while a published test uses it; a bulk "regrade a whole test" after a key
  correction is not offered (versions are pinned, so a corrected question affects new papers only, by design).

## Scaling notes

- **Papers** are prepared in the waiting room ahead of the start, so 200k students spread their preparation over the
  lead window; pool eligibility is cached per slot (`POOL_CACHE_SECONDS`).
- **Saves** are one Redis hash write; at 20k saves/s (200k students, one save per 10 s) the API tier, not the database,
  is the constraint — API processes are stateless, add more. The database sees flushes (batches per attempt), starts,
  submissions and grading.
- **Grading** scales by running more workers (`SKIP LOCKED`); the queue depth (`GET /internal/queue`) is the autoscaling
  signal. Partition `attempt_events`/`attempt_answers` by time when they reach billions of rows.
