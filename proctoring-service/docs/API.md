# Proctoring Service API

Base URL `/api/v1` (port 8008). The machine-readable contract is [openapi.json](openapi.json) (26 operations). Conventions are
the platform's ([lms-backend/README.md](../../README.md)): bearer token from user-management, ids are 64-bit numbers as
strings, success `{status, code:"SUCCESS", message, <resource>}`, errors `{status:"error", code, message, details[], request_id}`.

## Who may do what

| Caller | Can |
|---|---|
| **Student** | pre-check, upload/register snapshots, heartbeat, report events, read their own cases, appeal an invalidation |
| **Exam manager** (`exams.manage`) | monitor and control every session, review every case, decide appeals, read the media audit log |
| **Institution staff / head** | monitor and review *their own students'* sessions and cases on platform tests |
| **Employer members** | monitor and review sessions/cases of *their own* hiring assessments |
| **Other services** | `/internal/*` with `X-Internal-Service-Token` |

Another owner's session or case answers `404`, not `403`.

## The student's flow

```
POST /sessions {test_id}                         start the pre-check (returns requirements: consent, fullscreen, camera, …)
POST /sessions/{id}/snapshots/upload-url {kind}  strict: id_photo, then face_enrol   → presigned S3 POST
POST /sessions/{id}/snapshots {kind, key}        register the uploaded file
POST /sessions/{id}/precheck {consent, consent_version, browser, fullscreen_supported, camera, microphone, bandwidth_kbps, screen_share}
     → {ready: true}  and assessment-service will now start the test   (or failures[] to fix and retry)
   … the student starts the attempt in assessment-service; `attempt.started` makes the session active …
POST /sessions/{id}/heartbeat                    every heartbeat_interval_seconds: proof of life + staff directives
POST /sessions/{id}/events {events:[{type, occurred_at?, detail?}]}    batched browser events
POST /sessions/{id}/snapshots/upload-url {kind:"periodic"} + register   about every snapshot_interval_seconds (strict)
```

Strict sessions also send, per `requirements`: a `screen` capture with each periodic snapshot when `screen_share` is true (the
test requires sharing the entire screen; the pre-check fails `SCREEN_SHARE_REQUIRED` without it), and an `audio` clip
(`content_type` `audio/webm`, `audio_clip_seconds` long) every `audio_interval_seconds` for the voice check. The test's
`proctoring_screen_share` comes from assessment-service's `test.published`.

Event types a client may report: `fullscreen_exit`, `tab_switch`, `window_blur`, `copy_paste`, `right_click`,
`devtools_open`, `multiple_monitors`, `network_lost`, and (strict) `camera_off`, `mic_off`, `screen_share_stopped`. Others are
listed under `rejected` in the response. Each adds weighted risk capped per type; see [app/risk/policy.py](../app/risk/policy.py).

## Monitoring (`/monitor`)

`GET /monitor/sessions?test_id&status&min_risk&only_critical` (highest risk first) · `GET /monitor/sessions/{id}` (risk
breakdown, recent events, directives) · `POST .../warn {message}` · `POST .../pause {message?}` · `POST .../resume` ·
`POST .../terminate {message?}`. Pause, resume and terminate act on the attempt in assessment-service and are recorded only when
it agrees (`502 ASSESSMENT_UNAVAILABLE`: nothing changed; `409 ATTEMPT_NOT_CONTROLLABLE`: it refused).

## Integrity cases

`GET /cases?test_id&status&overdue` · `GET /cases/{id}` (report: `risk_breakdown`, `timeline`, `event_counts`, `snapshots`,
`ai_analysis` = `complete` / `partial` / `unavailable` / `not_applicable`) · `GET /cases/{id}/snapshots/{snapshot_id}/url`
(audited, short-lived) · `POST /cases/{id}/claim` · `POST /cases/{id}/decide {decision: reviewed_ok|invalidated, note}` (an
invalidation needs a written note) · `POST /cases/{id}/decide-appeal {outcome: upheld|overturned, note}` (exam managers, never
the first reviewer) · `GET /audit/media-access` (exam managers). Students: `GET /my/cases`, `POST /cases/{id}/appeal {reason}`.

Case `status`: `open` → `under_review` → `decided` → (`appealed` →) `final`. A low-risk attempt is `final` with
`decision: clear` and no reviewer.

## Internal

`POST /internal/snapshots/{id}/findings {findings:[{type, confidence, detail?}]}` — an asynchronous AI worker's results
(idempotent). `GET /internal/queue` — analysis backlog, sessions awaiting a decision, open and overdue cases.

## Codes

| Code | HTTP | Meaning |
|---|---|---|
| `TEST_NOT_PROCTORED` | 404 | the test has no proctoring (or is unknown) |
| `SESSION_NOT_ACTIVE` | 409 | events/snapshots/controls are only for a running test |
| `NOT_APPLICABLE` | 409 | snapshots are strict-only |
| `FILE_NOT_UPLOADED`, `INVALID_KEY`, `INVALID_TYPE` | 422 | the snapshot registration was refused |
| `CASE_NOT_OPEN`, `CASE_ALREADY_CLAIMED` | 409 | the case is decided / another reviewer is on it |
| `REASON_REQUIRED` | 422 | an invalidation needs a written reason |
| `APPEAL_NOT_ALLOWED`, `NO_APPEAL` | 409 | only an invalidation, once, within the window |
| `SAME_REVIEWER` | 403 | an appeal is decided by someone other than the first reviewer |
| `MEDIA_DELETED` | 404 | the snapshot passed its retention period |
| `ASSESSMENT_UNAVAILABLE` | 502 | assessment-service could not carry out a control; nothing changed |
