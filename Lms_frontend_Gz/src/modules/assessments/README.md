# Assessments module

> Status: **Done** · Backend: `lms-backend/assessment-service` · Roadmap: Phase 5
> Gated by the single `assessments` section from `GET /users/me/permissions` (students, institution staff/heads, `content.author`/`content.review`/`exams.manage` admins, and employers).

Three sections, each with its own `api/`, `types.ts`, `pages/`, `components/`, `routes.tsx` (see [src/modules/README.md](../README.md) for the shared layout rules):

- `questions/` — the question bank: all ten question types (`mcq_single`, `mcq_multi`, `true_false`, `fill_in`, `match`, `ordering`, `coding`, `sql`, `subjective`, `file_submission`), each with its own body/answer-key editor (`components/editors/`), plus the draft → in_review → published → superseded version lifecycle.
- `tests/` — test settings, the sections/slots builder (fixed questions or random pools by criteria), publish lifecycle + validation, exam schedules, and — as tabs on the test's own page rather than separate screens — results, analytics and the plagiarism signal.
- `attempts/` — "My tests" and the actual exam player (prepare → instructions → start → answer, autosaved, timed → submit → result), plus the staff side: the scoped attempts list, pause/unpause/terminate/regrade, and the grading queue for subjective/file answers.

`common/` holds the enums every section shares (`QuestionType`, `TestKind`/`TestStatus`, `AttemptStatus`/`AttemptResult`, `IntegrityStatus`, ...) and their labels/badges.

**Nav is deliberately thin.** Only "My tests" is a sidebar item — unlike most other modules, a student here gets a hard `403` reading a question or test definition (not just an empty list), so Question bank/Tests/Attempts/Grading queue would be broken links for most people with the `assessments` section. They're reached instead from My tests' own header actions, shown only when the viewer's role/scope actually allows it (see `routes.tsx`).

**The exam player is the one place in this frontend with real client-side state logic** (the countdown, per-question autosave with a client-owned revision counter, section timers) — still UI-only: the server is the sole authority on the deadline and re-checks it on every save; the client's timer is a display, and `useAnswerAutosave`'s revision numbers only need to keep increasing, never to match anything server-side (see `docs/API.md`: "revision is the client's change counter").

**Import:** `/questions/import` sends a JSON list of questions to `POST /questions/bulk` (with an Idempotency-Key) and shows each row's outcome; failed rows show the server's field messages. **Not built**: a rich read-only question preview (the editor is the only place to see a question's full structure).