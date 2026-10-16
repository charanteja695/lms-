# Support Service API

Base URL `/api/v1` (port 8012). Machine-readable contract: [openapi.json](openapi.json) (31 operations). Platform conventions
([lms-backend/README.md](../../README.md)): bearer token from user-management, ids are 64-bit numbers as strings, success
`{status, code:"SUCCESS", message, <resource>}`, errors `{status:"error", code, message, details[], request_id}`.

## Who may do what

| Caller | Can |
|---|---|
| **Student** | open tickets, read and reply on their own (never internal notes), close, rate |
| **Institution staff / head** | the `batch_staff` queue of their own institution; a head also assigns within it; institution canned replies |
| **Exam team** (`exams.manage`) | the `exam_team` (integrity) queue |
| **Support manager** (`support.manage`) / super admin | every queue, assign anywhere, SLA policies, platform canned replies |
| **ai-tutor-service** (internal token) | `POST /internal/tickets` |

## Student — `/tickets`

- `POST /tickets {subject, description, category: learning|technical|billing|integrity|access|other, course_id?}` with an optional
  `Idempotency-Key` → `201 {ticket}`. Rate limited per student.
- `GET /tickets?status&page&per_page`, `GET /tickets/{id}` → `{ticket, messages[]}` (public messages only, `requester_name`, `assignee_name`).
- `POST /tickets/{id}/replies {body}` → `{ticket, reply}`. Reopens a resolved ticket inside the reopen window; `409 TICKET_CLOSED`,
  `409 REOPEN_WINDOW_PASSED`.
- `POST /tickets/{id}/close`, `POST /tickets/{id}/csat {rating: 1..5, comment?}` (`409 NOT_RESOLVED`, `409 CSAT_ALREADY_SUBMITTED`).

A ticket: `{ticket_id, subject, category, queue, priority, status, source, course_id, requester_user_id, organization_id,
assignee_user_id, first_response_due_at, resolution_due_at, first_response_breached, resolution_breached, first_response_at,
resolved_at, closed_at, reopened_count, csat_requested_at, csat_rating, created_at, last_activity_at}`. A message:
`{message_id, seq, author_user_id, author_role, kind: public|internal, body, attachments: [{filename, content_type, size_bytes}], created_at}`.

## Attachments

- `POST /attachments/upload-url {filename, content_type, size_bytes}` (anyone who opens or answers tickets) →
  `{attachment: {key, upload: {url, fields}, expires_in}}`. `422 INVALID_FILE_TYPE` / `OUT_OF_RANGE` per `ATTACHMENT_ALLOWED_EXTENSIONS`
  and `ATTACHMENT_MAX_MB`. POST the file to `upload.url` with `upload.fields` (it goes straight to S3).
- `POST /tickets`, `POST /tickets/{id}/replies` and `POST /agent/tickets/{id}/replies` accept `attachments: [{key, filename}]` (up to
  `ATTACHMENT_MAX_FILES`). `422 NOT_YOUR_FILE` (another person's upload), `FILE_NOT_UPLOADED` (not in storage yet), `TOO_MANY_FILES`.
- `GET /tickets/{id}/messages/{message_id}/attachments/{index}` (the requester; public messages) and
  `GET /agent/tickets/{id}/messages/{message_id}/attachments/{index}` (an agent who handles it; internal notes too) →
  `{attachment: {filename, url, expires_in}}`, a short-lived download link. `404 ATTACHMENT_NOT_FOUND` / `MESSAGE_NOT_FOUND`.

## Agent — `/agent`

- `GET /tickets` — the queue this agent may see, active tickets by default. Filters `status`, `queue`, `priority`, `category`,
  `assignee` (`me` | `unassigned` | user id), `breached`, `q` (subject), `course_id`, `requester_id`; `sort=due|activity|created`.
- `GET /tickets/summary` → per queue `{open, assigned, waiting_on_student, unassigned, breached, oldest_unanswered_minutes}`.
- `GET /reports/sla?start&end` → `{tickets, resolved, first_response_breached, resolution_breached, first_response_compliance,
  resolution_compliance, avg_first_response_minutes, avg_resolution_minutes, csat_responses, csat_average, reopened, truncated}`
  over the agent's own queues (default: last 30 days).
- `GET /tickets/{id}` (with internal notes; `source_ref` is the tutor conversation for a hand-off), `GET /tickets/{id}/events` (audit trail). `404` when not your queue.
- `GET /tickets/{id}/transcript` — the tutor conversation behind an `ai-tutor` ticket, read from ai-tutor-service's internal API once this
  service has decided the agent may handle the ticket (message ids let the agent promote an answer to the tutor FAQ). `404 NO_TRANSCRIPT`
  for a portal ticket or a deleted conversation, `502 UPSTREAM_UNAVAILABLE` when ai-tutor does not answer.
- `POST /tickets/{id}/replies {body, internal?, then?: waiting_on_student|resolved, canned_reply_id?}`
- `GET /tickets/{id}/assignees` — who it may be assigned to (managers; a head for their batch_staff queue), the same rule `/assign` enforces: candidates of the queue who hold its permission right now (asked of user-management; `502` if it does not answer).
- `POST /tickets/{id}/claim` · `/assign {assignee_user_id}` (`422 ASSIGNEE_NOT_ELIGIBLE`, `403 CANNOT_ASSIGN`) · `/release` ·
  `/resolve` · `/reopen` · `/close`; `PATCH /tickets/{id} {priority?, category?}`.
  Errors: `409 ALREADY_ASSIGNED`, `409 NOT_ACTIVE`, `409 NOT_RESOLVED`, `409 TICKET_CLOSED`, `403 NOT_YOUR_QUEUE`.
- `GET /canned-replies`, `POST /canned-replies {scope: platform|organization, title, body}`, `PATCH /canned-replies/{id} {title?, body?, active?}`,
  `GET /canned-replies/{id}/render?ticket_id=` — fills `{{student_first_name}}` and `{{ticket_subject}}`.

## Administration — `/admin` (support manager)

`GET /sla-policies` (12 rows: every queue × priority, `is_default`), `PUT /sla-policies {queue, priority, first_response_minutes,
resolution_minutes}` (`409 INVALID_SLA_TARGETS`; applies to tickets created or re-prioritised from then on),
`DELETE /sla-policies/{queue}/{priority}` back to the default.

## Internal — `POST /internal/tickets`

Header `X-Internal-Service-Token`; optional `Idempotency-Key` (a retry returns the ticket already opened). Body `{requester_user_id,
organization_id?, subject, description, category = learning, source = "ai-tutor", source_ref?, reason?, course_id?}` →
`201 {ticket: {ticket_id, status, queue}}`. Unknown fields are rejected.

## Events

Every payload has `{ticket_id, requester_user_id, organization_id, category, queue, priority, status, assignee_user_id, occurred_at}` plus:
`ticket.created` `{source, course_id, first_response_due_at}` · `ticket.assigned` · `ticket.replied` `{message_id}` (public replies only) ·
`ticket.status_changed` `{previous_status, reopened?, reason?}` · `ticket.sla_breached` `{kind: first_response|resolution}` ·
`ticket.csat_requested` · `ticket.csat_submitted` `{rating}`. Consumed: `user.created/updated/suspended/activated/deleted`
(payload contract in `app/events/consumers/handlers.py`).
