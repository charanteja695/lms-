# Assessment Service API

Base URL `/api/v1` (port 8007). The full machine-readable contract is [openapi.json](openapi.json) (63 operations; import
it into Postman or a client generator; regenerate with `python scripts/export_openapi.py`). This page explains what the
schema cannot: the shapes that depend on a question's type, the flows, and the rules.

Conventions are the platform's ([lms-backend/README.md](../../README.md)): bearer access token from user-management,
ids are 64-bit numbers **as strings**, success `{status, code:"SUCCESS", message, <resource>}`, lists add `page_context`,
errors `{status:"error", code, message, details[], request_id}`. `Idempotency-Key` (8–80 chars) is honoured on creating a
question, a bulk import, a test and an attempt.

## Who may do what

| Caller | Can |
|---|---|
| **Student** | see their tests (`/my/tests`), prepare/start/resume/save/submit attempts, read their results. Cannot read questions or definitions |
| **Platform author** (`content.author`) | create/edit questions and tests, submit them for review |
| **Platform reviewer** (`content.review`) | approve/reject/retire questions and tests. Someone **other than the author** must approve (super admin exempt) |
| **Exam manager** (`exams.manage`) | schedule exams, see and control every attempt, grade and override, regrade, release results, reports |
| **Institution staff / head** | see, grade and pause/terminate *their own students'* attempts on platform tests; the grading queue for them |
| **Employer** (recruiter authors, employer admin approves) | their own questions and **hiring** tests only; results of their hiring assessments |
| **Other services** | `/internal/*` with `X-Internal-Service-Token` |

A platform test only uses platform questions, and an employer's hiring test only that employer's. Another owner's
question or test answers `404`, not `403`.

## Question types

`POST /questions` takes `{question_type, text, body, answer_key, explanation?, default_marks, difficulty 1-5, bloom?,
skills[], topics[], tags[]}`. `body` is what the student sees, `answer_key` what is correct (never sent to a student before
results). Ids inside a question (`id`) are 1–20 letters/digits/`-`/`_`.

| `question_type` | `body` | `answer_key` | Student's `response` | Marks |
|---|---|---|---|---|
| `mcq_single` | `{options:[{id,text}]}` (2–12) | `{correct:"id"}` | `{selected:"id"}` | all or nothing |
| `mcq_multi` | `{options:[…]}` | `{correct:["id"], scoring:"all_or_nothing"\|"partial"}` | `{selected:["id"]}` | partial = (right − wrong) / correct, never below 0 |
| `true_false` | `{}` | `{correct:true\|false}` | `{value:true\|false}` | all or nothing |
| `fill_in` | `{blanks:n}` (1–10) | `{blanks:[{answers:[…], case_sensitive?, tolerance?}], scoring}` | `{values:["text"\|null,…]}` | per blank if `partial`; `tolerance` compares numbers |
| `match` | `{left:[{id,text}], right:[{id,text}]}` (right may hold decoys) | `{pairs:{leftId:rightId}, scoring}` | `{pairs:{leftId:rightId}}` | per correct pair if `partial` |
| `ordering` | `{items:[{id,text}]}` | `{order:["id",…], scoring}` | `{order:["id",…]}` (every item) | per item in place if `partial` |
| `coding` | `{problem_id, languages?}` — a code-execution-service problem | `{scoring:"partial"\|"all_or_nothing"}` | `{language, source}` | the weighted test-case score (0–100) |
| `sql` | same as `coding` | same | `{language:"sqlite"\|"postgresql", source}` | same |
| `subjective` | `{rubric?:[{id,criterion,max_marks}], max_words?}` | `{model_answer?}` (for graders) | `{text}` | by a person: rubric scores or marks |
| `file_submission` | `{allowed_extensions?, max_files, max_size_mb, rubric?}` | `{}` | `{files:[{key,filename,size,content_type}]}` | by a person |

Negative marking (a test setting) costs a *wrong, answered* question `marks × percent` on MCQ, true/false and fill-in only,
and a score never drops below 0. An empty or `null` response clears the answer.

**File answers.** `POST /attempts/{id}/answers/{question}/file-upload-url` → a presigned S3 POST (`upload.url` +
`upload.fields`); upload directly, then save the answer with the returned `key`. The save is refused unless the file is
really in storage (the size recorded is storage's), belongs to this attempt and question, and matches the rules.

## Question lifecycle

`draft → in_review → published → superseded`, per **version**. `PATCH` edits the working draft; on a published question the
first edit opens a new version that starts as a copy. `POST /submit` (author) → `POST /approve` or `/reject` (reviewer).
`DELETE /questions/{id}/draft` drops an unpublished edit. `retire` is refused while a published test uses the question.
`GET /questions` filters by type, status, version status, difficulty range, Bloom, skill, topic, tag and text.

## Tests

`POST /tests` `{title, kind, target_id?, time_mode, duration_minutes?, pass_mark_percent, max_attempts (0 = unlimited),
cooldown_hours, score_counting, negative_marking_percent, shuffle_questions, shuffle_options, result_visibility,
review_policy, proctoring_level, requires_schedule, sections?}`.

- `kind`: `topic`, `module`, `final` (need the catalog `target_id`: topic / module / **course**), `practice`, `hiring`.
- `time_mode`: `overall` (needs `duration_minutes`) or `per_section` (every section needs `time_limit_minutes`).
- `result_visibility`: `immediate`, `after_window` (when the exam window closes, or its `results_release_at`), `manual`
  (`POST /tests/{id}/release-results`). `review_policy`: `none` (score only) or `answers` (each question with the correct
  answer and explanation once released).
- `PUT /tests/{id}/sections` replaces the structure: `{sections:[{title, instructions?, time_limit_minutes?, slots:[…]}]}`.
  A slot is `{slot_type:"fixed", question_id, marks?}` or `{slot_type:"pool", count, marks, criteria}` where
  `criteria = {types?, difficulty_min?, difficulty_max?, bloom?[], skills?[], topics?[], tags?[]}` — a question matches when
  it has **at least one** of the listed values of each kind given (any-of within a kind, all kinds must match) and is
  active and published. A pool never repeats a question already on the paper.
- Lifecycle `draft → in_review → published → retired`; publishing runs the full validation (`GET /tests/{id}/validation`)
  and freezes the test (`total_marks`, `question_count`). One published test per (kind, target). `clone` starts a new draft.
- **Schedules** (`/tests/{id}/schedules`, `exams.manage`): `{starts_at, ends_at, organization_id?, enforce_end,
  results_release_at?}`. A test with `requires_schedule` can only be started inside a window for the student's institution.

## Taking a test

```
GET  /my/tests                             what I can take, and if not, why (reason codes below), attempts left, cooldown
POST /tests/{id}/attempts {start_now?}     prepare the paper (the waiting room); returns the attempt already open if any
POST /attempts/{id}/start                  start the clock → paper + answers so far + remaining_seconds
PUT  /attempts/{id}/answers/{question}     autosave one answer   {response, revision, flagged}
PUT  /attempts/{id}/answers                autosave several      {answers:[{question_id, response, revision, flagged}]}
POST /attempts/{id}/resume                 after a refresh/crash: same paper, saved answers, time left (each resume is logged)
POST /attempts/{id}/finish-section         per-section tests: lock this section, open the next
POST /attempts/{id}/submit                 202: queued for grading
GET  /attempts/{id}/result                 status message → score/pass-fail once released (+ review if the test allows)
```

- `remaining_seconds` and `server_time` are the server's; the client clock is never trusted. Time up → `409 ATTEMPT_ENDED`
  on the next save (and the attempt is already submitted, reason `timeout`).
- `revision` is the client's change counter: an older revision never overwrites a newer one (the item comes back
  `status: "stale"`). Batches report each answer's `saved`/`stale`/`rejected` (with `error.code`) independently; the single
  `PUT` answers `422` for a rejected answer.
- The paper is only served while the attempt runs. After it ends the student reads results, not questions.
- **Staff**: `GET /attempts` (scoped by role), `GET /attempts/{id}/events` (audit trail), `POST /attempts/{id}/pause|unpause|
  terminate`, `POST /attempts/{id}/regrade`, `GET /grading/queue`, `PUT /attempts/{id}/answers/{question}/grade`
  `{rubric_scores | marks, feedback?}` (an override of an automatic grade needs `exams.manage` and `feedback`).
- **Reports** (`exams.manage` or the owning employer): `GET /tests/{id}/results`, `/results/export` (CSV, streamed),
  `/analytics`, `/plagiarism`.

## Internal endpoints

Authenticated with `X-Internal-Service-Token`, not a user: `POST /internal/assignments` (invite a candidate to a hiring
test), `POST /internal/attempts/{id}/pause|unpause|terminate`, `POST /internal/attempts/{id}/integrity {decision}`,
`GET /internal/queue` (autoscaling signal: grading and coding depth, answers awaiting flush).

## Error and reason codes

| Code | HTTP | Meaning |
|---|---|---|
| `NOT_ENROLLED` / `NOT_ELIGIBLE_FOR_FINAL` / `NOT_INVITED` | 403 | not enrolled in a course containing the test / modules not all complete / no invitation |
| `ATTEMPTS_EXHAUSTED` / `ALREADY_PASSED` | 409 | every attempt used / a final test already passed |
| `COOLDOWN` | 409 | `details[0].message` is `next_available_at` |
| `NOT_SCHEDULED` / `EXAM_NOT_OPEN` | 409 | no session for the student's institution / waiting room or exam not open (`details` has `opens_at`) |
| `NOT_YET_OPEN` / `INVITATION_EXPIRED` | 409 | hiring invitation window |
| `WAITING_ROOM` | 429 | exam is busy: retry after `Retry-After` seconds; the paper is already prepared |
| `ATTEMPT_ENDED` / `ATTEMPT_PAUSED` / `ATTEMPT_NOT_STARTED` | 409 | the attempt cannot take answers now |
| `SECTION_CLOSED` / `SECTION_NOT_OPEN` | 422 | per-section test: that section is finished / not yet reached |
| `INVALID_ANSWER`, `QUESTION_NOT_IN_ATTEMPT`, `FILE_NOT_UPLOADED` | 422 | the answer was refused |
| `VERSION_IN_REVIEW`, `TEST_NOT_DRAFT`, `TARGET_ALREADY_HAS_TEST`, `QUESTION_IN_USE` | 409 | lifecycle conflicts |
| `SELF_REVIEW_NOT_ALLOWED`, `OVERRIDE_NOT_ALLOWED` | 403 | four-eyes / only exam managers override |
| `PAPER_GENERATION_FAILED` | 503 | a pool no longer has enough questions; retry, and tell the author |
| `IDEMPOTENCY_KEY_REUSED` | 409 | the key was used for a different request |
