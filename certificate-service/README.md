# Certificate Service

> Status: **Done** · Roadmap phase: **6** · Local port: **8009** · Blueprint: [docs/PRODUCT.md](../../docs/PRODUCT.md) §5.4

Issues a verifiable certificate when a student passes a course's final test, renders it once as a PDF with a QR code,
serves a public verification lookup, and revokes it when an integrity case later invalidates the pass.

| | |
|---|---|
| Owns (own database) | certificate_templates, certificates, certificate_events, user_refs / institution_refs / course_refs (read-models), idempotency-free: processed_events, outbox_events |
| Emits events | `certificate.issued`, `certificate.revoked` |
| Consumes events | `course.passed`, `course.pass_revoked` (assessment-service) · `user.*`, `institution.*` (user-management) · `course.published` (catalog-service) |
| API | [docs/API.md](docs/API.md) · [docs/openapi.json](docs/openapi.json) (17 operations) |

Follows the service template in [lms-backend/README.md](../README.md): verifies tokens against user-management's JWKS
(never issues its own), checks the shared Redis access-state for revocation, transactional outbox to `lms:events`,
idempotent consumers (`processed_events`).

## What it does

- **Issue on pass.** `course.passed` (released, integrity-cleared — assessment-service decides that) creates a
  certificate: unique public `certificate_id`, an unguessable `verification_code` (in the QR code and URL), the
  student's name, course title, institution, completion date, score and **grade band**. Everything printed is
  **snapshotted** on the row, so it never changes when a profile or template later does. Idempotent by attempt; one
  live certificate per student and course (a revoked one doesn't block a later genuine pass — partial unique index).
- **Templates per course** (§5.4). Authors (`content.author`) write drafts — title, body and footer text with
  validated `{placeholders}`, accent colour, up to 3 signatories, grade bands — a reviewer (`content.review`)
  activates them, which archives the one it replaces. A course's own template beats the platform default, which beats
  the built-in one. `GET /certificate-templates/{id}/preview` renders a sample PDF.
- **PDF generated once** by the worker (reportlab + a QR from segno; byte-identical for identical input), stored in S3.
  The row is the job: claimed with `SKIP LOCKED` + a lease, so a dying worker loses nothing. If the student's name or
  the course title hasn't arrived from the other services yet, the render is retried with backoff instead of printing
  blanks; after `PDF_MAX_ATTEMPTS` it is `failed` and an exam manager can regenerate.
- **Public verification.** `GET /public/verify/{code}` needs no login and reveals only what is printed plus
  `valid` / `revoked` — never why, never ids of people. Rate limited per IP.
- **Revocation.** Automatically on `course.pass_revoked` (an integrity case invalidated the pass), or by an exam manager
  with a reason. The verification page then shows it revoked and the PDF is no longer handed to the student. Idempotent.
- **Sharing.** Each certificate carries its verification URL and a LinkedIn "Add to profile" link
  (`certId`, `certUrl`, issue month/year).
- **Who sees what.** A student their own; institution staff/head their institution's students'; exam managers all.

## Events

`certificate.issued` `{certificate_id, student_user_id, organization_id, course_id, version_id, attempt_id,
score_percent, grade, completion_date, issued_at, verification_url}` — career-service attaches it to the skill profile,
notification-service can tell the student. `certificate.revoked` `{certificate_id, student_user_id, organization_id,
course_id, reason, revoked_at}`. The consumed payloads are documented in `app/events/consumers/handlers.py`.

## Run

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements-dev.txt
cp .env.example .env && alembic upgrade head
uvicorn app.main:app --port 8009          # API
python -m app.worker                      # outbox relay, event consumer, PDF rendering
pytest -m "not postgres"                  # 29 tests (SQLite, fakeredis, moto)
pytest -m postgres                        # 3 tests on a real embedded PostgreSQL (pip install pgserver)
```

## Verification (2026-09-21)

**32 tests** — 8 unit (layout rules, deterministic PDF), 21 integration on SQLite, 3 on a **real PostgreSQL**
(migration up → down → up with `alembic check` finding no drift; concurrent deliveries of one pass issue one
certificate; concurrent PDF workers never claim the same certificate). ruff and `mypy --strict` clean.

### Not built / not verified

- **Not exercised here:** real S3 (moto only) and a real Redis (fakeredis). Nothing here proves PDF rendering in a
  viewer beyond producing a valid, deterministic PDF file; the layout has not been reviewed by eye on a printed page.
- **Fonts:** the PDF uses the built-in Helvetica, so a name with characters outside Latin-1 (e.g. Devanagari, Telugu)
  will not render correctly. Embedding a Unicode font is the next step for those names.
- **No logo/background images** in templates yet (text, colour and signatories only).
- **Names arrive from events only**: a student created before this service existed has no name here until their next
  `user.updated`; there is no backfill (their certificate's PDF is retried, then `failed` for an admin).
- **The verification page is an API** (`/public/verify/{code}`); the frontend hosts the page the QR code links to
  (`PUBLIC_VERIFY_BASE_URL`).
- No bulk export/report; no manual issuance (a missed `course.passed` is an event-delivery problem: the shared consumer
  retries a failing event and dead-letters it to `lms:events:dead` after 10 failures, which is where to look).
