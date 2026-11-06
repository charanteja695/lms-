# Proctoring module

> Status: **Done** · Backend: `lms-backend/proctoring-service` · Roadmap: Phase 6
> Gated by the single `proctoring` section (students, institution staff/heads, employer admins/recruiters, `exams.manage` admins).

Three sections (see [src/modules/README.md](../README.md) for the layout rules):

- `sessions/` — the student's pre-check at `/proctoring/precheck/:testId`: consent, system check (fullscreen, browser, estimated bandwidth) and, for strict tests, camera + microphone with the ID and face photos (uploaded straight to storage via presigned POST), and — when the test requires it (`requirements.screen_share`) — sharing the entire screen (`ScreenShareStep`; a window or tab is refused; the stream is held in `core/lib/screenShare.ts` so it survives the navigation to the exam). On success the session is remembered for that attempt (`core/lib/storage.ts` → `proctoringSessionStorage`) and the student returns to the attempt's instructions.
- `monitor/` — live sessions, highest risk first, with the risk breakdown, directives sent, and warn / pause / resume / terminate. Pause/resume act on the attempt in assessment-service, whose state proctoring-service doesn't expose, so both buttons stay available and the server decides (`409 ATTEMPT_NOT_CONTROLLABLE`).
- `cases/` — the integrity review queue and case report (risk breakdown, event counts, timeline, snapshots with audited view links), claim / decide / decide-appeal; the media audit log (exam managers); and the student's own cases with a one-time appeal.

**Nav:** one "Proctoring" item. `common/pages/ProctoringHomePage` sends students to their cases and everyone else to live monitoring; the cases list links to monitoring and (for exam managers) the audit log.

**The exam itself runs in assessments.** `AttemptInstructionsPage` routes a proctored attempt here for the pre-check first. During the attempt, `assessments/attempts/hooks/useExamProctoring` sends heartbeats (and shows staff warnings), reports the browser events docs/API.md lists, enforces fullscreen, blocks copy/paste and right-click, and for strict tests keeps the camera live and uploads periodic snapshots, records a short microphone clip every `audio_interval_seconds` (`useProctorAudio`), and, if the test requires screen sharing, uploads a screen frame with each snapshot (`useProctorScreen`); when sharing stops it reports `screen_share_stopped` once and `ScreenShareBanner` asks the student to share again. It calls proctoring-service through its own `api/proctoringClientApi.ts`, not this module's files (rule 5). The camera hook (`core/hooks/useCameraCapture`) and presigned upload (`core/lib/presignedUpload`) are shared infrastructure.

**Tests are shown by id** (`#<test_id>`): a test definition is readable only by authors/reviewers/exam managers and the owning employer, so resolving a title would 403 for institution staff and students.

**Not built / limits:** a page reload loses the screen share (the browser cannot keep it), so the student shares again and the gap is reported; audio clips need `MediaRecorder` with webm (Chrome, Edge, Firefox; not Safari); devtools detection is a window-size heuristic; bandwidth comes from `navigator.connection` when available (else 1000 kbps), and the server makes the pass/fail call. The proctoring session is stored per tab, so an attempt resumed in a new tab sends no client events (heartbeat loss is scored server-side).
