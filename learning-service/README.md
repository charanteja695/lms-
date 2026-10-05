# Learning Service

> Status: **Done** (v1) · Roadmap phase: **3** · Local port: **8005** · Blueprint: [docs/PRODUCT.md](../../docs/PRODUCT.md)

Batches, seat-checked enrolment, item/topic/module progress and unlock rules.

| | |
|---|---|
| Owns (own database) | institution_refs, course_version_refs + module/topic/topic_item refs (local read-models), batches, enrollments, item_progress, assessment_results (latest released topic/module test result per enrolment), outbox_events |
| Emits events | enrollment.created, enrollment.removed, topic_item.completed, topic.completed, module.completed, course.eligible_for_final (`enrollment.removed` also carries `student_user_id`, `version_id`; `course.eligible_for_final` carries `student_user_id`, so notification-service can address them) |
| Consumes events | institution.created/updated/suspended/activated/deleted, course.published, course.retired, attempt.finalized (assessment-service: topic and module tests only) |

Follows the service template and conventions in [lms-backend/README.md](../README.md): verifies
access tokens against user-management's JWKS (never issues its own), checks the shared Redis
access-state keys for revocation, and authorises by the `accounts.manage` scope or the
`institution_head` role — see [app/permissions/](app/permissions).

## Design notes (deviations from the original skeleton sketch worth knowing)

- **No `batch_staff` / `batch_courses` tables.** A batch is one institution's students on one
  course version — the skeleton's `batch_courses` implied many-to-many, but nothing in the
  product flow needs a batch to span multiple courses. Assigning staff to a batch isn't built
  either (see "Not yet wired").
- **No `notes`/`bookmarks`** yet — student-facing player features with no unlock-rule
  dependency; deferred rather than scoped down.
- **`title` on modules/topics/items, and `course_id`/`title` on a batch, exist for display only.**
  The original design stored and served only what unlock-rule computation needs (position, pass
  mark, test ids) — no display text, and `Batch` never carried its course's id, only its
  immutable `version_id`. Both were already present in catalog-service's `course.published`
  payload (`app/services/course_structure_service.py` simply wasn't persisting them) or trivially
  derivable (`Batch.course_version.course_id`/`.title`, once that relation is eager-loaded — see
  `app/models/batch.py`'s `course_id`/`title` properties). Added once the frontend needed to show
  real names instead of raw ids; no unlock-rule logic changed.
- **Entitlement checks read subscription-service's Redis cache directly**
  (`app/clients/entitlement_cache.py`), not a locally-mirrored `Subscription` table built from
  `subscription.*` events. The cache was built by subscription-service specifically so
  "is this institution entitled to this course?" is instant (docs/PRODUCT.md §6.1) — mirroring
  it into a second table here would just be a slower, harder-to-keep-consistent copy of the
  same fact. The actual seat *count* is never trusted from the cache though: reserving one
  always makes a real synchronous call to subscription-service, which is the only source of
  truth for whether a seat is actually free (see "Not yet wired" for the auth mechanism).
- **`course.published`'s full authoring tree is required.** This service can't evaluate unlock
  rules from ids alone, so catalog-service's `course.published` event was changed (in this same
  pass) to carry every module/topic/item with its pass mark and position — see catalog-service's
  `ReviewService._published_structure_payload`. No sync call back into catalog-service exists
  or is planned.
- **Completion follows the blueprint rule** (`app/services/completion.py`, a pure function): a topic is
  complete when its required items are done **and** its test, if it has one, is passed; a module when
  its topics are complete and its test is passed; the student is eligible for the final when every
  module is. "Passed" comes from assessment-service's `attempt.finalized` (only released results,
  `test_kind` topic/module), kept as the latest result per enrolment and test (`assessment_results`),
  ordered by `revision`. A pass survives a later failing retake; an integrity invalidation of the
  passing attempt takes it back (state is recomputed; no "un-completed" event exists). Milestone events
  fire exactly on the incomplete → complete transition, whether the last thing done was an item or a
  test. The unlock state gained `test_required` / `test_passed` on topics and modules.

## Flow

```
POST /batches                         institution_head (own institution) or accounts.manage
  -> reads the Redis entitlement cache directly; fails if there's no active subscription
POST /batches/{id}/enrollments        reserves a seat (sync call to subscription-service) before
                                       creating the enrolment; no seat, no enrolment, no exceptions
POST /enrollments/{id}/withdraw       releases the seat
POST /enrollments/{id}/items/{item_id}/complete   the enrolled student only; idempotent
GET  /enrollments/{id}/unlock-state   per-topic/module unlocked/completed state, computed on read
```

## Local development

```bash
cp .env.example .env    # set SUBSCRIPTION_SERVICE_URL / INTERNAL_SERVICE_TOKEN to match subscription-service
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8005   # http://localhost:8005/docs
python -m app.worker                          # outbox relay + inbound event consumer
pytest                                        # mocks subscription-service's HTTP calls with respx
```

`INTERNAL_SERVICE_TOKEN` must match the value subscription-service checks in its own
`app/api/deps.py::require_seat_caller` — they're two independent settings that happen to need
the same value, not a shared secret store (see subscription-service/README.md "Not yet wired").

## Tests

23 tests (`tests/unit`, `tests/integration`). Five cover test results gating completion (items alone don't complete a
topic with a test; pass topic then module test → completion events and eligibility; redelivered/older revisions ignored;
a later failing retake keeps a pass and an invalidation removes it; final/practice/unknown/withdrawn are ignored); the
migration was verified up → down → up with `alembic check` on a real PostgreSQL. The original 18 cover: authorization (missing token, wrong role,
institution head without an organisation, accounts.manage needing an explicit organization_id),
batch creation requiring an active entitlement and rejecting retired courses, cross-institution
visibility, the full enrol → withdraw flow with the seat reserve/release calls mocked (including
that a rejected reserve call leaves no enrolment behind and that a student can't double-enrol
actively in the same batch), that only the enrolled student can mark their own items complete
(idempotently), unlock-state computation reflecting real progress and final-test eligibility, and
the institution/course event consumers that build the local read-models. Migrations are verified
with a full upgrade → downgrade → upgrade cycle on both SQLite and a real PostgreSQL instance,
with autogenerate confirming no drift.

## Not yet wired

- **The internal-service token is a single shared secret**, not a real per-service identity
  scheme — same caveat as subscription-service's own README.
- **A test attached to a course version after it was published isn't required.** The requirement comes from the
  test ids in the `course.published` tree; catalog-service can attach a test to an already-published version
  (`test.published`) without re-emitting `course.published`, and that test then doesn't gate completion here.
- **Test results are not backfilled**: only `attempt.finalized` events after this consumer exists count.
- **Unlock mode `drip`** (a batch-scheduled release of topics) isn't scheduled; everything
  behaves like `sequential` regardless of what catalog-service's course rule says.
- **No staff-to-batch assignment**, no notes/bookmarks.
- **Enrol/withdraw is not fully atomic across services** (no distributed transaction exists):
  if subscription-service's seat call succeeds but this service's insert then fails, the
  reservation is released as a compensating action; if withdraw's local commit succeeds but the
  release call then fails, the seat stays reserved until someone retries the (idempotent)
  release. Acceptable for v1; would need an outbox-driven retry to close fully.
