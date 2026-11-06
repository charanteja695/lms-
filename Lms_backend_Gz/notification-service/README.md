# Notification Service

> Status: **Done** (v1) · Roadmap phase: **3** · Local port: **8016** · Blueprint: [docs/PRODUCT.md](../../docs/PRODUCT.md)

In-app and email notifications built from platform events, with editable templates and per-user
preferences.

| | |
|---|---|
| Owns (own database) | user_refs, course_refs (local read-models), notifications, deliveries, notification_preferences, notification_templates, processed_events, outbox_events |
| Emits events | notification.delivered, notification.failed |
| Consumes events | user.created/updated/suspended/activated/deleted, course.published, enrollment.created/removed, course.eligible_for_final, course_request.decided, subscription.activated/cancelled/expired |

Follows the service template and conventions in [lms-backend/README.md](../README.md): verifies
access tokens against user-management's JWKS (never issues its own) and checks the shared Redis
access-state keys for revocation.

## How it works

```
lms:events ──> inbound consumer ──> dispatch (once per event_id) ──> handler
                                                                      │  resolves recipients from the local
                                                                      │  user directory, renders the template
                                                                      ▼
                                          notifications row (in-app inbox, always)
                                          deliveries row    (email, if the type, address and preference allow)
                                                                      │
worker delivery loop ── claims due deliveries ── sends ── sent │ retry with backoff │ failed
                                                                      │
                                              outbox ──> notification.delivered / notification.failed
```

| Notification type | Sent to | Category |
|---|---|---|
| `enrollment.created`, `enrollment.removed` | the student | enrollment |
| `course.eligible_for_final` | the student | learning |
| `course_request.rejected` (from `course_request.decided`) | whoever made the request | subscription |
| `subscription.activated`, `.cancelled`, `.expired` | every active institution head of that institution | subscription |

An approved course request is not notified on its own: `subscription.activated` reaches the
institution heads instead, which avoids sending two messages for one approval.

## API (`/api/v1`)

| Endpoint | Who |
|---|---|
| `GET /notifications` (`unread`, `page`, `per_page`, `sort_order`), `GET /notifications/unread-count` | any signed-in user, own inbox only |
| `POST /notifications/{id}/read`, `POST /notifications/read-all` | any signed-in user (idempotent) |
| `GET /notification-preferences`, `PUT /notification-preferences` | any signed-in user; the response says which categories are `email_editable` |
| `GET /notification-templates`, `PUT /notification-templates/{type}/{channel}`, `DELETE /notification-templates/{type}/{channel}` | `super_admin` |
| `GET /deliveries` (`status`), `POST /deliveries/{id}/retry` | `super_admin` |

Another user's notification looks exactly like a missing one (404). Templates use `${placeholder}`
syntax and can only use the placeholders their notification type provides (listed in the
`variables` of `GET /notification-templates`); anything else is rejected with a field error. Delivery
responses never include the recipient's address.

## Design notes

- **A read-model of recipients, not a call to user-management.** Events carry ids only, so the
  service keeps `user_refs` (name, role, organisation, email, status) from the `user.*` events and
  `course_refs` (titles) from `course.published`. Suspended and deleted users are skipped.
- **Every event is handled at most once.** The stream is at-least-once, and a repeat must not send
  a second email, so `processed_events` records each `event_id` in the same transaction as its
  effects. The worker prunes it after `PROCESSED_EVENTS_RETENTION_DAYS`. (The other services'
  consumers rely on idempotent upserts instead; here a duplicate is user-visible.)
- **In-app is the record; email is a copy.** The inbox row is always written. Email is a separate
  `deliveries` row so it can retry independently, and it stores the rendered subject and body so a
  retry never depends on templates edited since.
- **Deliveries are claimed with a lease**, not held under a row lock while SMTP is slow: a sweep
  pushes `next_attempt_at` out by `DELIVERY_CLAIM_LEASE_SECONDS`, sends, then records the result.
  A worker that dies mid-send simply lets the lease expire. Failures back off exponentially
  (`DELIVERY_RETRY_BASE_SECONDS`, capped) and give up after `DELIVERY_MAX_ATTEMPTS`, at which point
  a super admin can retry.
- **Preferences are decided by the backend.** Users choose per category whether it is also
  emailed; the subscription category is locked on because those are operational notices. The
  frontend renders `email_editable` and never mirrors the rule.
- **Producer payloads were extended for this service** (additive fields only, following the
  `course.published` precedent): `course_request.decided` now carries `organization_id`,
  `course_id`, `requested_by`; `subscription.cancelled` / `.expired` carry `organization_id` and
  `course_id`; `enrollment.removed` carries `student_user_id` and `version_id`;
  `course.eligible_for_final` carries `student_user_id`. An event from before that change is
  skipped with a warning, never failed.
- **Password-reset and account-setup emails stay in user-management.** They carry one-time secrets
  that should not travel over the event bus, so they are not notifications.

## Local development

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
python scripts/generate_env_example.py && cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8016     # http://localhost:8016/docs
python -m app.worker                            # outbox relay, event consumer, email sender, housekeeping
pytest
```

`EMAIL_BACKEND=console` (default) logs emails instead of sending them and is refused in
staging/production; set `EMAIL_BACKEND=smtp` with the `SMTP_*` settings there.

## Tests

40 tests (`tests/unit`, `tests/integration`): template rendering and placeholder validation
(including that a template cannot read attributes or run code); every event type turning into the
right notifications for the right people; duplicate events, users without an email, users unknown
to the directory, suspended and deleted users, and events from before the producers were extended;
the inbox API (own rows only, unread filter, idempotent read, read-all, pagination); preferences
(locked categories, opt-out keeps the inbox row); template overrides and reset; email delivery
(success, HTML escaping, backoff, giving up, lease, super-admin retry, no addresses in responses).

The migration was verified with a full upgrade → downgrade → upgrade cycle and a drift check on both
SQLite and a real PostgreSQL (`pgserver`), and the service flow (events → notifications → claimed
by exactly one of two workers → sent → outbox) was run on that PostgreSQL. The wire format was
checked through the real publisher and `StreamConsumer` on fakeredis.

## Not yet wired

- **SMS, WhatsApp and push.** Only in-app and email exist. A new channel is a value in
  `app/domain/enums.py::Channel` plus a sender in `app/channels/`; the delivery loop currently only
  sends email.
- **No backfill of users created before this service first ran.** The consumer group starts at the
  end of the stream (like every service's). Such a user still gets in-app notifications addressed
  by id, but no email, and cannot be resolved as an institution head, until their next `user.*`
  event. A backfill needs a replay or an internal listing endpoint in user-management.
- **Content reviewers are not notified of `course.submitted`.** Finding them needs admin scopes,
  which `user.*` events do not carry.
- **No deep links in emails** beyond `${app_url}`: frontend routes do not exist yet. In-app
  notifications carry the ids the frontend needs in `data`.
- **English only, one template per type and channel**, platform-wide. No per-institution
  branding or locale.
- **A failing event is retried, then dead-lettered.** If handling raises (e.g. a database outage), the
  message stays unacked; the shared `StreamConsumer` reclaims it after 60 s and, after 10 failed
  deliveries, moves it to `lms:events:dead`. Handlers are idempotent on `event_id`, so a retry is safe.
- **Not run against a real Redis.** There is none on the development machine; the blocking
  consumer loop in `app/worker/runner.py` follows the other services' worker and is untested
  beyond that.
