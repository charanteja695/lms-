# LMS Backend

Microservice backend for the LMS platform. Each domain ("management") is an independent
service in its own folder, with its own database, migrations, tests and Docker image.

Full product flow and roadmap: [docs/PRODUCT.md](../docs/PRODUCT.md).

| Phase | Service | Folder | Port | Status |
|---|---|---|---|---|
| 0 | User Management (auth, 2FA, hierarchy, users, admins, institutions, employers, permissions API, audit log, import/export, events) | [user-management/](user-management/) · [API](user-management/docs/API.md) | 8001 | Done |
| 0.5 | Shared package (JWKS verification, envelopes, ids, pagination, access-state, event consumer) | [shared/](shared/) | — | Done |
| 0.5 | API Gateway (routing, token checks, rate limits, CORS) | [api-gateway/](api-gateway/) | 8000 | Done |
| 1 | Catalog (course → module → topic → items, versions) | [catalog-service/](catalog-service/) | 8002 | Done |
| 1 | Media (clip upload, transcoding, signed playback) | [media-service/](media-service/) | 8003 | Done |
| 2 | Subscriptions (course requests, seats, entitlements) | [subscription-service/](subscription-service/) | 8004 | Done |
| 3 | Learning (batches, enrolments, progress, unlock rules) | [learning-service/](learning-service/) | 8005 | Done |
| 3 | Notifications (in-app and email; SMS, WhatsApp, push not yet) | [notification-service/](notification-service/) | 8016 | Done |
| 4 | Code Execution (online compiler, judge, SQL, plagiarism signal) | [code-execution-service/](code-execution-service/) | 8006 | Done |
| 5 | Assessments (question bank, tests, attempts, grading, results, hiring assessments) | [assessment-service/](assessment-service/) · [API](assessment-service/docs/API.md) | 8007 | Done |
| 6 | Proctoring (pre-check, live events + snapshots, risk score, live monitoring, integrity review + appeal) | [proctoring-service/](proctoring-service/) · [API](proctoring-service/docs/API.md) | 8008 | Done |
| 6 | Certificates (issue on pass, PDF + QR, public verification, revoke) | [certificate-service/](certificate-service/) · [API](certificate-service/docs/API.md) | 8009 | Done |
| 7 | AI Gateway (provider routing/fallback, prompt registry, quotas & cost, redaction, moderation, audit log) | [ai-gateway/](ai-gateway/) · [API](ai-gateway/docs/API.md) | 8010 | Done |
| 7 | AI Tutor (course-grounded tutor + support agent) | [ai-tutor-service/](ai-tutor-service/) · [API](ai-tutor-service/docs/API.md) | 8011 | Done |
| 7 | Support (tickets, SLAs) | [support-service/](support-service/) · [API](support-service/docs/API.md) | 8012 | Done |
| 8 | Career (skill profile, AI resume builder) | [career-service/](career-service/) · [API](career-service/docs/API.md) | 8013 | Done |
| 9 | Job Portal (jobs, matching, AI shortlist, pipeline) | [job-portal-service/](job-portal-service/) · [API](job-portal-service/docs/API.md) | 8014 | Done |
| 10 | AI Interview (mock + screening interviews) | [ai-interview-service/](ai-interview-service/) · [API](ai-interview-service/docs/API.md) | 8015 | Done |
| 11 | Analytics (warehouse, dashboards, reports) | [analytics-service/](analytics-service/) · [API](analytics-service/docs/API.md) | 8017 | Done |
| 11 | Billing (quotes, GST invoices, payments) | [billing-service/](billing-service/) · [API](billing-service/docs/API.md) | 8018 | Done |

## Conventions for every service

Copy the structure of `user-management/`:

```
<name>-service/
├── app/{api,core,db,domain,events,middleware,models,permissions,repositories,schemas,services,utils,validators,worker}
├── alembic/            own migrations, own database
├── tests/{unit,integration}
├── Dockerfile  requirements.txt  pyproject.toml  .env.example  README.md
```

1. **Database per service.** Never read another service's tables. Share data through APIs or events.
2. **Authentication.** Verify access tokens with the User Management JWKS endpoint; do not issue tokens.
3. **Authorization.** Keep policy rules in `app/permissions/`, and scope data by the token's `org` claim (`organization_id`); refer to people by `user_id` only.
4. **API.** Version under `/api/v1` and use the shared envelopes: `{status, code, message, <resource>}` and `{status: "error", code, message, details, request_id}` (see user-management/docs/API.md).
5. **Events.** Write domain events to a transactional outbox table; consume others from the Redis Stream `lms:events` (de-duplicate on `event_id`).
6. **Revocation.** Before trusting a verified token, check the Redis access-state keys that user-management maintains (`lms:access:session|user|org:*`); see `user-management/app/core/access_state.py`.
7. **Configuration.** Read every setting from the service's env file: `.env` locally, `.env.docker` under compose. Generate the examples with `python scripts/generate_env_example.py`.
8. **Operations.** Expose `/health/live` and `/health/ready`, emit JSON logs with `request_id`, and propagate `X-Request-ID`.

## Local stack

The compose file runs PostgreSQL (a `databases` one-shot creates each service's own database), Redis, MinIO (S3-compatible,
with a `buckets` one-shot) and, for each of the ten built services, a migrate job, the API and a worker built from one image.

```bash
cd lms-backend
cp .env.example .env                                   # stack settings (ports, database user, MinIO credentials)
for s in */.env.docker.example; do cp -n "$s" "${s%.example}"; done   # every service's own settings (keeps existing files)

# 1. migrate every service (starts postgres and creates the databases first)
docker compose --profile tools up $(docker compose --profile tools config --services | grep -- '-migrate$')
# 2. start everything
docker compose up -d                                   # user-management is on http://localhost:8001/docs, catalog 8002, ...
# 3. first admin
docker compose exec user-management python -m app.cli create-super-admin --email ... --username ... --first-name ... --last-name ...
```

Host ports: user-management 8001, catalog 8002, media 8003, subscription 8004, learning 8005, code-execution 8006, assessment
8007, proctoring 8008, certificate 8009, notification 8016 (change them in `.env`); MinIO 9000 (API) and 9001 (console).
A single service: `docker compose up -d catalog-service catalog-service-worker`. Images use `lms-backend/` as the build
context (they install `shared/`), so build one by hand with `docker build -f catalog-service/Dockerfile -t lms-catalog-service .`.

Things the stack does not give you:
- **Judge0.** code-execution-service judges through Judge0, which is not part of this compose file; `JUDGE0_URL` points at
  `host.docker.internal:2358` for one running on your machine. Without one, nothing can be judged.
- **Browser-reachable object storage.** Pre-signed upload/download URLs carry `http://minio:9000`, a name only containers
  resolve, so a browser cannot use them as they are (there is no separate public-endpoint setting yet). For local browser tests
  map `minio` to `127.0.0.1` in your hosts file, or use real S3.
- **A shared internal token.** `INTERNAL_SERVICE_TOKEN` defaults to the same development value everywhere, which is what
  makes service-to-service calls work locally; change it in *every* `.env.docker` together, never in just one.
- **Verification.** This compose setup, the Dockerfiles and the shell helpers were written on a machine without Docker: the
  YAML, references, ports, buckets and databases are checked statically (and every `.env.docker.example` loads through its
  own service's settings), but `docker compose up` has not been run.
