# AI Tutor Service API

Base URL `/api/v1` (port 8011). Machine-readable contract: [openapi.json](openapi.json) (30 operations). Platform conventions
([lms-backend/README.md](../../README.md)): bearer token from user-management, ids are 64-bit numbers as strings, success
`{status, code:"SUCCESS", message, <resource>}`, errors `{status:"error", code, message, details[], request_id}`.

## Who may do what

| Caller | Can |
|---|---|
| **Student** | availability, conversations (own), messages, escalate, feedback, published FAQ they can see |
| **Institution staff / head** | FAQ of their own institution (write, promote a tutor answer, publish) |
| **Course author** (`content.author`) | a course's FAQ, evaluation sets and runs, feedback summaries, index status |
| **Support manager** (`support.manage`) | every FAQ, the escalation list and retry |
| **AI manager** (`ai.manage`) | `GET /index/status`, `POST /index/reindex` |
| **support-service** (internal token) | `GET /internal/conversations/{id}` — the transcript behind a ticket |

## Student

- `GET /availability` → `{enabled, reason, attempt_id, blocked_until}`. `enabled: false` (`GRADED_TEST_IN_PROGRESS`) inside a graded test.
- `POST /conversations {mode: "learning"|"support", course_id?}` — a learning conversation needs a course the student is enrolled in
  (`403 NOT_ENROLLED`, `422 COURSE_REQUIRED`).
- `GET /conversations`, `GET /conversations/{id}` (with messages), `DELETE /conversations/{id}`.
- `POST /conversations/{id}/messages {content, context: {item_id?, code?, language?, hint_request?}, stream}` with an `Idempotency-Key`.
  `context.item_id` is the lesson / practice problem the student has open; `hint_request: true` is the hint button (each request climbs
  the hint ladder one rung). Response `{turn: {user_message, assistant_message, escalation?}}`; a message is
  `{message_id, role, kind, content, citations, confidence, retrieval, hint_level, created_at}` with `kind` one of `answer`, `faq`,
  `low_confidence`, `escalation`, `blocked`, `question`. A lesson citation is `{type:"lesson", number, item_id, item_title, topic_title,
  module_title, item_type, source: "item"|"transcript", start_seconds, score, implicit}`; a FAQ citation `{type:"faq", faq_id, question}`.
  - `stream: true` answers `application/x-ndjson`: `{"type":"start","user_message":…}`, `{"type":"delta","text":…}`…, then
    `{"type":"message","message":…}` — or `{"type":"error","code","message"}` if the model fails midway (nothing half-written is saved).
    Errors that are HTTP errors stay HTTP errors: they are raised before the stream starts.
  - Errors: `403 TUTOR_DISABLED_IN_TEST`, `403 TUTOR_DISABLED_FOR_ORGANIZATION`, `429 QUOTA_EXCEEDED` (the institution's AI quota),
    `503 TUTOR_UNAVAILABLE` (the student's message *is* saved; retry with the same key), `422 ITEM_NOT_IN_COURSE`, `409 CONVERSATION_CLOSED`.
- `POST /conversations/{id}/escalate` — "talk to a person"; same hand-off as asking in words.
- `POST /messages/{id}/feedback {rating: "up"|"down", comment?}` — re-rating replaces.
- `GET /faq?course_id&q` — published FAQ entries visible to the student (platform, their institution, their courses).

## FAQ management (`/faq/manage`)

`GET` (paged, filters `status`, `scope`, `course_id`), `POST {scope, organization_id?, course_id?, question, answer}` (a draft),
`POST /promote {message_id, scope?}` (a tutor answer becomes a draft — staff default to their institution, authors to the course),
`PATCH /{id}`, `POST /{id}/publish`, `POST /{id}/archive`. `403 FAQ_SCOPE_FORBIDDEN` outside your scope.

## Authors

- `GET /feedback/summary?course_id` → `{up, down, down_rate}`; `GET /feedback/downvoted?course_id` → the unhelpful Q&A, no user ids.
- `GET /eval-sets?course_id` (newest first), `POST /eval-sets {course_id, name}`, `GET /eval-sets/{id}`, `POST /eval-sets/{id}/cases {question, expected_item_ids[]}`
  (`422 UNKNOWN_ITEM`), `POST /eval-sets/{id}/runs {version_id?, top_k?}` → `{method, top_k, case_count, hits, hit_rate, mrr, results[]}`,
  `GET /eval-runs/{id}`. `method` says whether retrieval was `dense` or `lexical`.
- `GET /index/status?course_id` → per version `{chunks, embedded_chunks, job_status, job_attempts, last_error}`.

## Operations

- `GET /escalations?status`, `POST /escalations/{id}/retry` (support manager; only a `failed` one, else `409 NOT_FAILED`).
- `POST /index/reindex {version_id}` (AI manager) — forget a version's vectors and embed again.
- `GET /internal/conversations/{id}` — internal token; the full transcript for the agent who received the ticket.

## Events

Emits `tutor.escalated` `{escalation_id, conversation_id, student_user_id, organization_id, course_id, reason, category, occurred_at}`
(when the hand-off is recorded, before the ticket exists) and `tutor.feedback` `{message_id, conversation_id, student_user_id,
organization_id, course_id, rating, message_kind, occurred_at}`. Consumed payloads are documented in `app/events/consumers/handlers.py`.

## The ticket it opens (support-service `POST /api/v1/internal/tickets`)

`{organization_id, requester_user_id, subject, description, category: learning|technical|billing|integrity|access, source: "ai-tutor",
source_ref: <conversation id>, reason, course_id}` with `Idempotency-Key: <escalation id>`; answers `{ticket: {ticket_id}}`.
