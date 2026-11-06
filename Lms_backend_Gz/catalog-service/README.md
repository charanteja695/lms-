# Catalog Service

> Status: **Done** (v1 authoring) · Roadmap phase: **1** · Local port: **8002** · Blueprint: [docs/PRODUCT.md](../../docs/PRODUCT.md)

Course authoring and publishing: course → module → topic → items (video, notes, practice, topic test), module tests, final test link, versions and learning paths.

| | |
|---|---|
| Owns (own database) | courses, course_versions, modules, topics, topic_items, learning_paths, learning_path_items, course_rules, reviews, outbox_events |
| Emits events | course.submitted, course.published, course.retired |
| Consumes events | media.ready, transcript.ready, test.published |

Follows the service template and conventions in [lms-backend/README.md](../README.md), the same way as [user-management](../user-management/):
verifies access tokens against user-management's JWKS (never issues its own), checks the shared
Redis access-state keys for revocation, and authorises by the `content.author` / `content.review`
scopes carried in the token — see [app/permissions/scopes.py](app/permissions/scopes.py).

## Content lifecycle

```
draft --submit--> in_review --approve--> published vN (immutable) --retire--> archived
  ^                   |
  '-------reject------'      new draft (v(N+1)) can start once no draft/in-review version is open
```

A course's modules, topics and topic items only exist inside a `course_version` row and can only
be edited while that version is `draft` (see `app/api/v1/authoring_deps.py::draft_version`).
Submitting requires every module to have a topic and every topic to have an item
(`ReviewService._ensure_content_complete`).

`course.published` carries the **full authoring tree** (modules → topics → items, pass marks,
positions, the course rule), not just ids — this is what lets subscription-service and
learning-service build their unlock-rule read-models purely from the event stream, with no
service-to-service call back into this service (see `ReviewService._published_structure_payload`).
`course.submitted` / `course.retired` stay lightweight (course id, version id, title, slug).

## Local development

```bash
cp .env.example .env                      # edit DATABASE_URL / REDIS_URL / USER_MANAGEMENT_JWKS_URL
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8002  # http://localhost:8002/docs
python -m app.worker                        # outbox relay + inbound event consumer
pytest
```

## Tests

**Who can read what.** Course and learning-path listings (titles and status) need a sign-in: every role names courses
somewhere (course requests, prices, job requirements). A course version's content needs a reader permission
(`catalog.read`, `catalog.browse`, `content.author`, `content.review`, or platform staff), and an unpublished version or
learning path is visible only to its authors and reviewers (others get 404). The review trail is authors/reviewers only.

27 tests (`tests/unit`, `tests/integration`) cover: authorization (missing token, missing scope,
correct scope), course CRUD and pagination, the full draft → submit → approve/reject → retire
lifecycle including the "empty course" and "already immutable" guards, module/topic reorder,
learning path authoring (add/remove/reorder courses, publish/archive), the inbound event
consumers, and one end-to-end pass through the real `lms_common` JWKS + access-state chain
(signature verification, expiry, revocation) rather than the dependency override the rest of the
suite uses for speed.

Migrations are verified with a full upgrade → downgrade → upgrade cycle on both SQLite and a real
PostgreSQL instance, with autogenerate confirming no drift against the models afterwards.

## Not yet wired (depends on services that don't exist yet)

- `module_test_id` / `topic_test_id` / `course_rules.final_test_id` are filled in by the
  `test.published` event once **assessment-service** exists.
- `topic_items.media_ready` / `transcript_ready` are filled in by `media.ready` / `transcript.ready`
  once **media-service** exists.
- `GET /courses` and `GET /courses/{id}` are intentionally open (no token required): there is no
  subscription/entitlement boundary yet. Revisit once **subscription-service** defines who may
  browse the catalogue.
