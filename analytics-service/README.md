# Analytics Service

> Status: **Done** · Roadmap phase: **11** · Local port: **8017** · Blueprint: [docs/PRODUCT.md](../../docs/PRODUCT.md) §5.9

Read-only dashboards and scheduled reports built from every other service's events. It authors nothing and calls no other
service synchronously — everything it shows is a number traceable to real events it has ingested. **PostgreSQL, not
ClickHouse** (the service map's original line): D12 in the blueprint, a deliberate deviation for this environment — see
"Known limits".

| | |
|---|---|
| Owns (own database) | event_facts, daily_rollups, enrollment_refs, report_definitions, report_runs, outbox_events, processed_events |
| Emits events | `report.ready` |
| Consumes events | ~30 event types from ten other services — the full list and exact payload fields are in `app/ingest/extract.py`'s registry, each checked against its producer's real code, not guessed |

## The rules that shape the design

1. **Every number traces back to a real event.** `app/ingest/extract.py` documents, for each event type this service
   tracks, exactly which payload field becomes which column — never invented, always the producer's real, shipped field
   name at the time it was written.
2. **A rollup is a cache, never the source of truth.** `DailyRollup` is recomputed from `EventFact` by upserting a fresh
   sum for a day (`app/aggregations/rollup.py`) — safe to re-run, safe for two workers to run at once (the unique key
   serialises them; both compute the same total from the same committed rows), and a bug fix or a new metric just
   replays history instead of needing a backfill migration.
3. **"Near-real-time", precisely defined.** A dashboard always reads `DailyRollup`, never `EventFact`, directly — the
   worker's rollup tick (`ROLLUP_INTERVAL_SECONDS`, default 5 minutes) recomputes the trailing `ROLLUP_TAIL_DAYS + 1`
   days on every pass, so "today" is at most one tick stale. There is no separate "read the live tail" code path.
4. **Two tenant axes, not one.** Some events belong to an institution (`organization_id`), some to a hiring company
   (`employer_id`), and a few carry both because the same fact matters to each side differently (an application's
   stage matters to the candidate's institution and to the hiring employer). `EventFact`/`DailyRollup` keep both
   columns rather than picking one, so a dashboard can filter on whichever axis is its own.
5. **Sees only your own tenant, unless your scope says otherwise.** An institution head/staff sees their own
   institution's dashboard; an employer's own team sees their own hiring funnel; every other dashboard is platform-wide
   and needs the scope that already manages that domain elsewhere (`content.review`, `exams.manage`, `support.manage`,
   `careers.manage`, `ai.manage`, `billing.manage`) or the catch-all `analytics.view` — see `app/permissions/policy.py`.

## What is where

- **Ingestion** (`app/ingest/extract.py`, `app/services/ingest_service.py`): one inbound-event router
  (`app/events/consumers/router.py`) for every event type, unlike most services here which map specific types to
  specific handlers — the registry decides per type what (if anything) is kept. Three learning-service events
  (`topic.completed`, `module.completed`, `course.eligible_for_final`) and three assessment-service ones
  (`course.passed`, `course.failed`, `course.pass_revoked`) carry only an `enrollment_id`, not an organisation, so
  `EnrollmentRef` (built from `enrollment.created`) resolves it — the same "consume the event, build a local
  read-model" pattern every service here uses instead of a synchronous call.
- **Rollups** (`app/aggregations/rollup.py`): the worker recomputes the trailing window on a timer (rule 3 above);
  `python -m app.worker` runs this alongside the usual outbox relay and inbound consumer.
- **Dashboards** (`app/services/dashboard_service.py`, `app/api/v1/endpoints/dashboards.py`): seven fixed shapes —
  institution, content (platform-wide learning funnel), exam integrity, support, hiring, AI usage & cost, billing &
  revenue — each a handful of numbers, never a raw list, built from one shared query (`app/services/rollup_query.py`).
- **Scheduled reports** (`app/services/report_service.py`, `app/api/v1/endpoints/reports.py`): save a dashboard +
  filters + a frequency; the worker runs it when due, reusing the exact same dashboard function a live `GET` uses, and
  emits `report.ready`. The rendered file (CSV or JSON) is kept in the database, not object storage — see limits.

## Running

```
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
pip install -e ../shared --config-settings editable_mode=compat   # what mypy needs to see lms_common's types
alembic upgrade head && uvicorn app.main:app --port 8017
python -m app.worker        # outbox relay, event consumer, rollup ticks, scheduled reports, housekeeping
```

Docker: `docker compose up analytics-service-migrate analytics-service analytics-service-worker` from `lms-backend/`.

## Verified

`ruff` and `mypy --strict` clean; **28 tests**: unit (extraction for a direct organisation id, a null one, the
`EnrollmentRef` backfill, an untracked event type being silently skipped, `ai.usage`'s two-field token sum, a missing
dimension being the "none" sentinel; rollup summing correctly across organisations and dimensions, and re-running a day
replacing rather than accumulating it) and integration over SQLite (an institution seeing only its own numbers and
being refused another's, a careers manager/analyst reading any institution, every platform dashboard's scope check
including the `analytics.view` catch-all, the content dashboard's computed pass rate, an employer's own hiring funnel
defaulting correctly and being refused another employer's, the billing dashboard reading as empty-but-wired before
billing-service exists, report creation's validation-before-permission ordering, a report hidden from someone who
doesn't own it, run-now producing a downloadable CSV, deactivation stopping the worker from picking a report up, and
the worker actually running a due report and rescheduling it), plus PostgreSQL through an embedded server (`pgserver`):
migration up→down→up with no drift from the models, the same event id ingested twice at once producing one `EventFact`
row (the unique constraint wins the race), and two workers recomputing the same rollup day at once leaving one
consistent row (Postgres rejects `date = varchar` outright, which SQLite silently tolerates — a real bug the SQLite
suite could not have caught; fixed by binding `date` objects, not ISO strings, in the rollup's `IN (...)`.)

The billing dashboard was wired before billing-service existed; once it did, its **real** emitted payloads (a full
subscription → invoice → payment → credit note flow and a plan purchase) were fed through this service's ingestion,
and are committed as a contract test (`test_billing_services_real_events_ingest_...`). A dashboard test then totals
such events (amounts in paise).

**Not exercised:** real Redis (fakeredis), Docker at runtime, a live user-management token round trip, and the two
services running against each other over a real Redis stream (each side is tested against the other's real payloads,
never through the stream itself).

## Known limits

- **PostgreSQL, not ClickHouse** (D12): fine at this project's real scale, a real limit at "billions of events a
  day" scale — the migration path is a new store behind the same `rollup_totals` read API, not a rewrite of the
  dashboards or the worker.
- **No per-course drill-down on the content dashboard.** The events this service ingests carry a topic or module id,
  not a course id or title — resolving one to a course's name would mean either a synchronous call to
  catalog-service (which this service, by design, never makes) or consuming and locally indexing catalog-service's
  full course/module/topic hierarchy, neither of which is built.
- **Two proctoring-service events carry no organisation at all** (`integrity.flagged`, `integrity.decided` — only a
  `user_id`): the exam-integrity dashboard is platform-wide only. Resolving a user to their institution would need a
  `UserRef` this service does not build; every other dashboard's organisation comes directly from its event's own
  payload or, for the three learning/assessment events named above, from `EnrollmentRef`.
- **A scheduled report's rendered file lives in this service's own database** (`ReportRun.content`, a `bytea`
  column), not object storage — fine for a handful of small CSVs per definition, a real limit if reports grow large
  or numerous; `REPORT_RUN_RETENTION_COUNT` bounds how many are kept per definition, but nothing prunes the content
  of old runs beyond that count today.
- **PDF rendering was not built** — reports are CSV or JSON only, not the "simple server-rendered PDF summary" an
  earlier draft of the blueprint mentioned; dropped to keep this phase's scope honest rather than half-built.
- **`report.ready` is emitted but nothing consumes it yet** — notification-service would need a new template and
  consumer handler to actually deliver a report by email/in-app, the same one-line addition every other producer/
  consumer pair here started as (see job-portal-service's `interview.completed` before ai-interview-service existed).
