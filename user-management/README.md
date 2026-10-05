# User Management Service

Identity provider for the LMS: authentication, two-factor login, users, admins, institutions, employers,
permissions, the audit log, bulk import, exports, background jobs and domain events. Other microservices trust
the access tokens it issues and read the revocation state it publishes.

**Stack:** Python 3.12 · FastAPI · PostgreSQL 16 · Redis · SQLAlchemy 2 (async) · Alembic · Argon2id · JWT · TOTP

| Document | Purpose |
| --- | --- |
| [docs/API.md](docs/API.md) | Full API reference: requests, responses, filters, errors, roles, data rules |
| [docs/openapi.json](docs/openapi.json) | OpenAPI 3 spec (also live at `/docs`) |
| [docs/postman/](docs/postman/lms-user-management.postman_collection.json) | Postman collection; login stores tokens automatically |

Regenerate the spec and collection after any API change: `python scripts/generate_api_artifacts.py`.

---

## What it does

| Area | Capabilities |
| --- | --- |
| Authentication | Login by email or username, refresh-token rotation with reuse detection, logout (one or all devices), device sessions, forgot/reset password with OTP or link, change password, account lockout |
| Two-factor | TOTP apps, recovery codes, replay protection, mandatory per role (`MFA_REQUIRED_ROLES`), admin reset for lost phones |
| Users | Create, get, partial update, suspend/activate, soft delete, revoke sessions, set a temporary password, self-service profile; role-specific data (employment, student + academic placement + guardians) |
| Hierarchy | Super admin → admin → institution (head → staff → student) and → employer (employer admin → recruiter), enforced on every request |
| Organisations | Institutions and employers share `organization_id`; admins own them per scope (`accounts.manage`, `careers.manage`) |
| Permissions for clients | `allowed_actions` per record, `GET /users/me/permissions`, `GET /users/form-options`: the UI renders from these instead of copying rules |
| Accounts without email | Students may sign in by username; a one-time temporary password is generated and shown once |
| Audit log | Everything is recorded and readable through `GET /audit-logs`, scoped per role |
| Lists | Filters, search, sorting, pagination with bounded counts |
| Bulk | CSV import (dry run, all-or-nothing or skip-invalid) directly or as a background job up to 50,000 rows with a report, CSV export (streamed or background job with email) |
| Integration | `user.*`, `institution.*`, `employer.*` and `access.*` events on Redis Stream `lms:events`; JWKS (RS256, with key rotation) for token verification; Redis access-state keys so every service drops revoked tokens within seconds |
| Operations | Audit log, health probes, JSON logs with request ids, housekeeping, statement timeouts |

## Architecture

```
app/
├── api/            deps (auth chain, services), session cookie, examples, responses; v1/endpoints: auth, users, admins, institutions, employers, audit_logs, jobs, health
├── services/       business rules: auth, mfa, user, institution (and employers), import, export, job, session, audit, audit log, rate limiter
├── repositories/   database queries
├── models/         tables: users, profiles, guardians, institutions, sessions, MFA, jobs, audit, outbox
├── schemas/        request/response contracts and validated field types
├── permissions/    roles, scopes, the authorization policy and the capabilities clients render from (single source of truth)
├── validators/     role-specific data rules
├── events/         outbox relay + Redis Stream publisher
├── worker/         background worker (export jobs, events, housekeeping)
├── notifications/  email senders and templates
├── core/ db/ middleware/ utils/ cli/
```

Dependencies point one way: `api → services → repositories → models`. Every public identifier is a 64-bit id sent as a
string (`user_id`, `organization_id`, `session_id`, `job_id`); internal UUID keys never leave the service.

## Running locally

```bash
python -m venv .venv
.venv\Scripts\activate                     # Windows (source .venv/bin/activate on Linux/macOS)
pip install -r requirements-dev.txt
copy .env.example .env                     # set secrets

alembic upgrade head
python -m app.cli create-super-admin --email owner@example.com --username owner --first-name Platform --last-name Owner
uvicorn app.main:app --reload --port 8001  # API
python -m app.worker                       # worker (second terminal)
```

Docker: from `lms-backend/`, see the header of [../docker-compose.yml](../docker-compose.yml) (API, worker, PostgreSQL, Redis).

## Tests and quality

```bash
pytest                                                      # SQLite + fake Redis, no services needed
set TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/lms_test
pytest                                                      # same suite on PostgreSQL
ruff check . && ruff format --check .
```

93 tests cover authentication, two-factor login, hierarchy and scope isolation, validation, filters, exports, import,
background jobs, event publishing and housekeeping.

## Migrations

Never edit an applied migration. For each model change: `alembic revision --autogenerate -m "..."`, review, `alembic upgrade head`,
then `alembic check`. Trigram search indexes need the `pg_trgm` extension (standard in PostgreSQL images and managed services);
the migration skips them with a warning where it is missing.

## Production checklist

- `ENVIRONMENT=production`, explicit `TRUSTED_HOSTS`, `CORS_ORIGINS`, `EMAIL_BACKEND=smtp`
- `JWT_ALGORITHM=RS256` with keys from `scripts/generate_jwt_keys.py`; other services use `/.well-known/jwks.json`
- Strong `TOKEN_HASH_SECRET` and `MFA_ENCRYPTION_KEY` from a secret manager
- `JOB_STORAGE_DIR` on storage shared by API and worker instances
- Run at least one worker; scale API and worker instances horizontally; PgBouncer for many instances
- The service refuses to start in staging/production with development secrets, console email or `DEBUG`
