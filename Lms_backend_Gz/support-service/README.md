# Support Service

> Status: **Done** · Roadmap phase: **7** · Local port: **8012** · Blueprint: [docs/PRODUCT.md](../../docs/PRODUCT.md) §5.5

The help desk: students open tickets, agents work queues, and the service keeps the clocks. Tickets are routed by category to
the batch's staff, to platform support, or to the exam team; each has SLA timers, canned replies, internal notes, a CSAT rating
afterwards and an audit trail. [ai-tutor-service](../ai-tutor-service/) hands conversations over through an internal endpoint.

| | |
|---|---|
| Owns (own database) | tickets, ticket_messages, ticket_events (audit), sla_policies, canned_replies; read-model: user_refs; outbox_events, processed_events |
| Emits events | `ticket.created`, `ticket.assigned`, `ticket.replied`, `ticket.status_changed`, `ticket.sla_breached`, `ticket.csat_requested`, `ticket.csat_submitted` |
| Consumes events | `user.created/updated/suspended/activated/deleted` (user-management) — names, role and institution of people |
| Called by | ai-tutor-service (`POST /internal/tickets`, internal token) |
| Calls | ai-tutor-service `GET /internal/conversations/{id}` (the transcript behind a hand-off ticket, for the agent handling it) |
| API | [docs/API.md](docs/API.md) · [docs/openapi.json](docs/openapi.json) (31 operations) |

## Lifecycle (`app/services/ticket_service.py`)

`open → assigned → waiting_on_student → resolved → closed`

- **Routing:** learning → `batch_staff` (the requester's own institution's staff), technical / billing / access / other →
  `platform_support`, integrity → `exam_team` (starts at `high` priority). Changing the category re-routes the ticket, which
  returns to its new queue unassigned. `support.manage` sees and handles every queue.
- **Replying:** a public agent reply is the *first response* and assigns the ticket to the replier if nobody has it; an internal
  note is never shown to the student and does not count as a response. `then` on a reply moves it to `waiting_on_student` or
  `resolved` in one call. Only the assignee (or a manager) can release; two agents claiming at once → one `409 ALREADY_ASSIGNED`.
- **Assignment** (`support.manage`, or an institution head inside their own queue) checks the assignee against `user_refs`: an
  active staff/head of the same institution for `batch_staff`, an active admin for the other queues — and then asks
  user-management (`POST /internal/permission-holders`, `USER_MANAGEMENT_URL`) whether they hold, right now, the permission
  that queue needs (`support.agent`; `exams.manage` or `support.manage`; `support.manage`), so a person whose permission a
  super admin removed is neither listed nor accepted. If user-management does not answer, assigning fails with `502`.
- **SLA:** two clocks from the *anchor* (creation, or the last reopen) — first response and resolution — with defaults per
  priority (`app/core/config.py`) overridable per queue and priority in `sla_policies`. Time spent `waiting_on_student` does
  not count: on resume the paused time pushes both due times out. The worker's sweep flags each breach once
  (`ticket.sla_breached`) and never flags a paused or already-answered clock. Changing priority recomputes the due times.
- **Resolve → CSAT:** resolving asks for a 1–5 rating (once, resolved or closed tickets only). A student reply on a resolved
  ticket reopens it within `REOPEN_WINDOW_DAYS`; after that, or when closed, `409`. Resolved tickets nobody answered
  auto-close after `AUTO_CLOSE_AFTER_DAYS`.
- **Idempotent creation:** `Idempotency-Key` on both the portal and internal endpoints. A retry that races the first request
  loses on the unique key and receives the winner's ticket — never a second ticket.
- **Attachments** (`app/services/attachment_service.py`): `POST /attachments/upload-url` checks type and size
  (`ATTACHMENT_ALLOWED_EXTENSIONS`, `ATTACHMENT_MAX_MB`) and returns a presigned POST under `support/{uploader}/`, so the bytes
  go straight to S3. A new ticket or a reply lists `{key, filename}` (up to `ATTACHMENT_MAX_FILES`); each key must be the
  author's own and already in storage (size and type are read back from S3, never trusted from the client). Downloads are
  short-lived links following the message's visibility: an attachment on an internal note is never reachable by the student.
- **Visibility:** a student sees only their own tickets and never internal notes; an agent who cannot handle a ticket gets
  `404`, not `403`, so existence is not revealed.

Every change takes a row lock on the ticket first, so simultaneous replies get consecutive message numbers and the SLA clock
cannot be paused twice.

## Running

```
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
pip install -e ../shared --config-settings editable_mode=compat   # what mypy needs to see lms_common's types
alembic upgrade head && uvicorn app.main:app --port 8012
python -m app.worker                                               # outbox relay, user events, SLA sweep, housekeeping
```

Docker: `docker compose up support-migrate support-api support-worker` from `lms-backend/` (see `.env.docker.example`).

## Verified

`ruff` and `mypy --strict` clean; **45 tests**: unit (SLA arithmetic, handling/assignment rules) and integration over SQLite
(routing, visibility, replies and internal notes, pause/resume, breach sweep, claim/assign/release, re-routing, resolve/CSAT/
reopen/close/auto-close, canned replies, SLA policies, summary and report, the tutor's exact hand-off payload, user events),
plus PostgreSQL through an embedded server (`pgserver`): migration up→down→up with no drift from the models, five agents
claiming one ticket (one wins), eight simultaneous replies (numbers 1..9, no gaps), six simultaneous retries of one key
(one ticket), concurrent SLA sweeps (each breach flagged once).

**Not exercised:** real Redis (fakeredis in tests), Docker/compose at runtime, a real user-management token/JWKS round trip,
the running worker loop against a live stream (its pieces are tested individually).

## Known limits

- SLA is wall-clock minutes; there is no business-hours calendar.
- Assignee eligibility uses role and institution only — `user.*` events carry no admin scopes, so an admin is assumed able to
  handle `platform_support`/`exam_team`; the handler check on the ticket itself still uses the token's scopes.
- No virus scanning of attachments and no email/reply-by-mail; no notification-service wiring for `ticket.*` yet (the events are emitted).
- Reports are computed in the service over at most 20 000 tickets per query (`truncated` says so); larger periods need an export job.
- Queue counts are computed per request; fine for a help desk's active set, not for millions of open tickets.
