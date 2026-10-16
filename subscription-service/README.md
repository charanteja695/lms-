# Subscriptions Service

> Status: **Done** (v1) · Roadmap phase: **2** · Local port: **8004** · Blueprint: [docs/PRODUCT.md](../../docs/PRODUCT.md)

Institution course requests, approval workflow, subscriptions (courses × seats × term), atomic
seat reserve/release, and the Redis entitlement cache other services will read.

| | |
|---|---|
| Owns (own database) | institution_refs, course_refs (local read-models), course_requests, subscriptions, seat_reservations, outbox_events |
| Emits events | course_request.submitted, course_request.decided, subscription.activated, subscription.cancelled, subscription.expired (`course_request.decided` also carries `organization_id`, `course_id`, `requested_by`, and `subscription.cancelled/expired` carry `organization_id`, `course_id`, so notification-service can address them) |
| Consumes events | institution.created/updated/suspended/activated/deleted, course.published, course.retired |

Follows the service template and conventions in [lms-backend/README.md](../README.md): verifies
access tokens against user-management's JWKS (never issues its own), checks the shared Redis
access-state keys for revocation, and authorises by the `accounts.manage` scope or the
`institution_head` role carried in the token — see
[app/permissions/scopes.py](app/permissions/scopes.py) / [app/permissions/roles.py](app/permissions/roles.py).

## Design notes (deviations from the original skeleton sketch worth knowing)

- **No separate `Plan` entity.** The original sketch listed "plans" as owned data, but with no
  pricing model yet (billing-service is phase 11, not started — see docs/PRODUCT.md §10 D8),
  a plan would just be a name with no behaviour. Seats and term length are carried directly on
  the course request / subscription instead; reintroduce `Plan` once pricing needs it.
- **No `subscription_courses` / `seat_allocations` tables.** A subscription is already
  course-scoped (one row per institution × course), so a join table added nothing. Individual
  seat occupancy (*which* student holds a seat) belongs to learning-service's enrolment records,
  not here — this service only tracks the atomic seat *count*, via `seat_reservations`, which
  exists purely to make reserve/release idempotent (see app/services/seat_service.py).
- **`institution_refs` / `course_refs` are local read-models**, not owned data. This service
  never reads user-management's or catalog-service's tables directly (see
  lms-backend/README.md §1): a course can only be requested once its `course.published` event
  has been consumed, and an institution once its `institution.created` event has been consumed.
  The primary key of each is the institution's/course's own public id — these tables are pure
  caches, never themselves exposed as a resource with an id of their own.

## Flow

```
POST /course-requests                    institution_head, own institution only
  -> validates the institution is active and the course is published (against the local refs)
POST /course-requests/{id}/approve       accounts.manage -> creates the Subscription
POST /course-requests/{id}/reject        accounts.manage
POST /subscriptions/{id}/cancel          accounts.manage
POST /subscriptions/{id}/seats/reserve   internal-service token (or accounts.manage), atomic, idempotent on reservation_key
POST /subscriptions/{id}/seats/release   internal-service token (or accounts.manage), atomic, idempotent on reservation_key
[worker] every 10 min: expire subscriptions whose ends_at has passed (no event triggers this)
```

Every subscription lifecycle change re-syncs (or removes) its Redis entitlement cache key
(`{ENTITLEMENT_KEY_PREFIX}:{organization_id}:{course_id}`) so a future learning-service can
answer "is this student's institution entitled to this course, with a free seat?" in under 5ms
without calling this service per check (see docs/PRODUCT.md §6.1).

## Local development

```bash
cp .env.example .env
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8004   # http://localhost:8004/docs
python -m app.worker                          # outbox relay + inbound consumer + expiry sweep
pytest
```

## Tests

23 tests (`tests/unit`, `tests/integration`) cover: authorization (missing token, wrong role,
institution head without an organisation, seat endpoints rejecting calls with neither a valid
internal token nor an accounts.manage session), the full course-request lifecycle (unknown
course, duplicate pending request, cross-institution visibility, approve creating an active
subscription with seat/term overrides, reject with a reason and re-requesting afterwards),
subscription cancellation, atomic seat reserve/release including idempotent retries and the
"no seats left" case, the institution/course event consumers that build the local read-models,
and the term-based expiry sweep. Migrations are verified with a full upgrade → downgrade →
upgrade cycle on both SQLite and a real PostgreSQL instance, with autogenerate confirming no drift.

## Not yet wired

- **The internal-service token is a single shared secret** (`INTERNAL_SERVICE_TOKEN`, checked
  via the `X-Internal-Service-Token` header — see app/api/deps.py::require_seat_caller), not a
  real per-service identity/credential scheme. Fine for now with one caller (learning-service);
  revisit if more services need to call in, or before this is internet-facing.
- **The entitlement cache has a reader now** (learning-service, see ../learning-service). The
  write side here (`app/entitlements/cache.py`) predates it and needed no changes.
- **Pricing/billing.** No cost, invoicing or payment fields exist anywhere in this service —
  see "No separate Plan entity" above.
