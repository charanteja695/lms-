# Analytics Service API

Base URL `/api/v1` (port 8017). Machine-readable contract: [openapi.json](openapi.json) (16 operations). Platform conventions
([lms-backend/README.md](../../README.md)): bearer token from user-management, ids are 64-bit numbers as strings, success
`{status, code:"SUCCESS", message, <resource>}`, errors `{status:"error", code, message, details[], request_id}`.

## Who may see what

| Caller | Sees |
|---|---|
| **Institution head / staff** | their own institution's dashboard (`GET /dashboards/institution`, no `organization_id` needed: it defaults to their own) |
| **Employer admin / recruiter** | their own company's hiring funnel (`GET /dashboards/hiring`, no `employer_id` needed: it defaults to their own) |
| **Platform admin holding the domain's scope** | that platform-wide dashboard — `content.review` → content, `exams.manage` → exam-integrity, `support.manage` → support, `careers.manage` → hiring (any employer), `ai.manage` → ai-usage, `billing.manage` → billing |
| **`analytics.view`** | every dashboard, platform-wide — the catch-all for someone whose job is analytics itself, not managing one domain |
| **Super admin** | everything |

Every dashboard takes `?days=` (1–90, default 7: how many trailing days including today).

## Dashboards — `/dashboards`

- `GET /institution?organization_id=&days=` → enrolments, topic/module completions, eligible-for-final, test results
  (finalized/passed/failed/invalidated, pass rate), certificates issued/revoked, students placed. `403
  NOT_YOUR_ORGANIZATION` for another institution without a platform scope.
- `GET /content?days=` → platform-wide: enrolments, topic/module completions, eligible-for-final, courses
  passed/failed/pass-revoked, course pass rate, average pass percent. No per-course breakdown — see the README.
- `GET /exam-integrity?days=` → platform-wide: attempts finalized (and by result), average percent, integrity flags (by
  stage), integrity decisions (by outcome). Platform-wide only — proctoring-service's events carry no organisation.
- `GET /support?days=&organization_id=` → tickets created (by category), status changes (by status), SLA breaches (by
  kind), CSAT responses and their average.
- `GET /hiring?days=&employer_id=&organization_id=` → applications by pipeline stage, placements (and average CTC),
  offers extended/accepted/declined/expired, interviews completed (AI recommendation mix), human review overrides.
  Send neither id for the platform-wide view (needs `careers.manage` or `analytics.view`); send `employer_id` for one
  company's own jobs; send `organization_id` for one institution's own students' hiring outcomes.
- `GET /ai-usage?days=&organization_id=` → calls (by capability), total cost (cents), total tokens.
- `GET /billing?days=&organization_id=` → invoices issued/paid/overdue/voided and their amounts, credit notes, plans
  activated/expired. From billing-service's events; amounts are paise. `plan.*` events carry the employer, so `organization_id` shows only an institution's invoices.

## Scheduled reports — `/reports`

- `POST` `{name, dashboard, filters: {organization_id?, employer_id?}, frequency: daily|weekly|monthly, format:
  csv|json}` → `201`. The same permission check as reading that dashboard live applies at creation time; the
  institution dashboard requires `filters.organization_id` (`422 REQUIRED` without it).
- `GET` — my own saved reports. `GET /{id}` — 404 for one you don't own (even a super admin's own reports are scoped
  this way; use the dashboard endpoints directly for someone else's numbers).
- `POST /{id}/deactivate` — stops the worker picking it up; does not delete past runs.
- `POST /{id}/run-now` → `201` — runs it immediately (the last 7 days), independent of its schedule.
- `GET /{id}/runs` — past runs (status, row count, when). `GET /{id}/runs/{run_id}/download` — the rendered file
  (`text/csv` or `application/json`); `409 RUN_NOT_READY` if the run failed or is still in progress.

## Events

Emitted: `report.ready {report_id, run_id, user_id, organization_id?, name, dashboard, format}` — nothing consumes
this yet (see the README).

Consumed: see `app/ingest/extract.py`'s registry for the full, exact list — roughly 30 event types across
learning-service, assessment-service, proctoring-service, certificate-service, job-portal-service,
ai-interview-service, support-service, ai-gateway, ai-tutor-service, and billing-service (docs/PRODUCT.md §5.10, not
built yet but wired ahead of time). Every field name in that registry is the producer's real, shipped payload field.
