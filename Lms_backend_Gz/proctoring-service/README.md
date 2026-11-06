# Proctoring Service

> Status: **Done** · Roadmap phase: **6** · Local port: **8008** · Blueprint: [docs/PRODUCT.md](../../docs/PRODUCT.md) §5.3

Monitors proctored tests: the pre-check, the live event stream and snapshots, a weighted risk score, live monitoring with
warn / pause / terminate, and the integrity decision — cleared automatically when the risk is low, otherwise decided by a
person, with one appeal.

| | |
|---|---|
| Owns (own database) | test_refs (read-model), proctor_sessions, proctor_events, snapshots, directives, integrity_cases, media_access_log, processed_events, outbox_events |
| Emits events | `integrity.flagged`, `integrity.decided` |
| Consumes events | `test.published/retired`, `attempt.started`, `attempt.submitted` (assessment-service) |
| Calls | assessment-service `POST /internal/attempts/{id}/pause\|unpause\|terminate\|integrity`; an AI analyzer over HTTP (optional); S3 |
| API | [docs/API.md](docs/API.md) · [docs/openapi.json](docs/openapi.json) (26 operations) |

Follows the service template in [lms-backend/README.md](../README.md): verifies tokens against user-management's JWKS
(never issues its own), checks the shared Redis access-state, transactional outbox to `lms:events`, idempotent consumers.

## What it does

- **Two levels** (§5.3). `basic`: fullscreen required, tab/window switch, copy/paste, right-click and devtools events, IP and
  device logged, a single live session. `strict`: everything in basic plus a working camera and microphone, a bandwidth check,
  an ID photo and a face photo (identity match), periodic snapshots, screen and audio capture, and AI detection.
- **Pre-check** (`POST /sessions`, `/precheck`). Consent to the *current* consent text, the system check, and for strict the
  identity photos. When it passes the session is `ready` and a short-lived Redis key `lms:proctor:ready:{user}:{test}` is
  published — **assessment-service will not start a proctored test's clock without it** (`PROCTORING_PRECHECK_REQUIRED`).
- **Live events and risk.** The browser reports events in batches; each type adds weighted points **capped per type**
  ([app/risk/policy.py](app/risk/policy.py): fifty tab switches cost no more than five), the score is capped at 100. Clients
  cannot report AI findings or staff actions, and a client clock cannot backdate the timeline. A quiet client is scored once per
  gap; a changed IP or device is scored. Crossing `RISK_FLAG_MIN`, or any critical finding, raises `integrity.flagged` once.
- **Single active session.** Starting an attempt links the pre-checked session and supersedes any other open session of that
  student and test (a second live one is scored). A student who started without a pre-check still gets a session, and the
  missing pre-check is scored.
- **Snapshots** go straight to S3 (presigned POST; bytes never pass through here), are registered only if they really exist,
  and are queued for analysis (`SKIP LOCKED` + lease; retried with backoff). **Under load** only every Nth periodic snapshot is
  analysed; with **no analyzer configured** they are stored and marked skipped, and the report says
  `ai_analysis: "unavailable"` — it never reads as "looked and found nothing".
- **AI analysis is a contract, not built in** ([app/clients/analyzer.py](app/clients/analyzer.py)): any HTTP service returning
  findings (`no_face`, `multiple_faces`, `different_person`, `identity_mismatch`, `phone_detected`, `book_detected`,
  `looking_away`, `voices_detected`, each with a confidence) plugs in via `AI_ANALYZER_URL`, or pushes results to
  `POST /internal/snapshots/{id}/findings`. Findings below `AI_MIN_CONFIDENCE` score nothing; the rest score in proportion to
  confidence.
- **Live monitoring.** Exam managers, the student's institution staff (platform tests) and an employer's members (its hiring
  assessments) see running sessions, highest risk first, and can warn (delivered with the next heartbeat), pause, resume or
  terminate. Pause/resume/terminate act on assessment-service's attempt and are recorded only once it agrees (`502` means
  nothing changed). Terminating is a critical event: a person then reviews the attempt.
- **The decision** (`attempt.submitted`). After a bounded wait for pending analysis the integrity report is built (risk
  breakdown, timeline, counts, flagged snapshots, analysis status). **Low risk and nothing critical → cleared automatically**
  (`integrity.decided: clear`). Anything else → a case for a person, who claims it and decides `reviewed_ok` or `invalidated`;
  **an invalidation needs a written reason** — nothing in this service ever invalidates an attempt by itself. The decision is
  emitted *and* pushed straight to assessment-service, so a decision does not depend on the event stream alone.
- **Appeal.** The student may appeal an invalidation **once**, within `APPEAL_WINDOW_DAYS`; a **different** exam manager decides
  it. Overturning emits `integrity.decided: reviewed_ok`; upholding is final.
- **Privacy** (§5.3, DPDP). Consent is required and versioned; snapshots are deleted from storage after
  `MEDIA_RETENTION_DAYS` (default 90, metadata and the timeline stay); every view of a snapshot is logged before the link is
  issued (`GET /audit/media-access`, exam managers only); reviewers see only what their scope allows and an employer's
  assessment is never visible to the candidate's institution.

## Event contracts

Emitted: `integrity.flagged {attempt_id, session_id, status: "flagged" | "under_review", risk_score, case_id?}` and
`integrity.decided {attempt_id, decision: "clear" | "reviewed_ok" | "invalidated", case_id, session_id, test_id, user_id,
automatic, risk_score, appeal?}` — assessment-service applies them (`ResultService.integrity_flagged/decided`).
Consumed (assessment-service): `test.published` `{test_id, title, kind, proctoring_level, organization_id}`,
`attempt.started` `{attempt_id, test_id, user_id, organization_id, proctoring_level}`, `attempt.submitted`
`{attempt_id, proctoring_level, submit_reason}`.

## Run

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements-dev.txt
cp .env.example .env && alembic upgrade head
uvicorn app.main:app --port 8008          # API
python -m app.worker                      # outbox relay, event consumer, analysis, decisions, retention
pytest -m "not postgres"                  # 61 tests (SQLite, fakeredis, moto)
pytest -m postgres                        # 4 tests on a real embedded PostgreSQL (pip install pgserver)
```

## Verification (2026-09-21)

**66 tests** — 8 unit (risk policy), 53 integration on SQLite, 4 on a **real PostgreSQL** (migration up → down → up with
`alembic check` finding no drift; one session per attempt however many deliveries race; one decision per session however many
workers race; concurrent analysers never share a snapshot). ruff and `mypy --strict` clean. Also verified against
assessment-service: its `attempt.started` / `test.published` payload keys are the ones consumed here, and its new
pre-check gate is covered by 4 tests there.

### Not built / not verified

- **No detection is built in.** Face, phone, book, gaze and voice detection need a model or a vendor behind
  `AI_ANALYZER_URL` (or ai-gateway, phase 7). Everything around it — queue, contract, retries, sampling, scoring, reports — is
  built and tested against a stand-in; **no real analyzer, and no real camera/browser client, has been exercised**.
- **Not exercised here:** real S3 (moto only), real Redis (fakeredis), and assessment-service itself (its internal API is mocked
  to the documented contract).
- **The browser side is the frontend's job**: fullscreen enforcement, blocking copy/paste and right-click, capturing snapshots,
  audio and screen share, and reporting events. This service can only score what a client reports, and a hostile client can
  omit events; the periodic snapshots, heartbeats and AI findings are the independent evidence.
- **No live push**: monitors poll `GET /monitor/sessions`; students receive warnings with their next heartbeat (≤
  `HEARTBEAT_INTERVAL_SECONDS`), not instantly.
- **Consent text and its versions live in the frontend/config** (`CONSENT_VERSION`); there is no consent-management API, and no
  per-student media export/erasure endpoint yet (retention deletes on schedule).
- `proctor_events` is a single table indexed for range partitioning by `occurred_at`; partitioning is not set up.
- Assessment-service's pre-check gate lets a start through if Redis cannot be read (an outage must not lock every student out);
  a deployment that prefers to fail closed needs that changed there.
- Inbound events that raise are retried by the shared consumer (reclaimed after 60 s, dead-lettered to `lms:events:dead` after
  10 failures); decisions are additionally pushed synchronously to assessment-service, `attempt.started/submitted` are not.
