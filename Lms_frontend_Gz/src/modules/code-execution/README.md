# Code Execution module

> Status: **Done** · Backend: `lms-backend/code-execution-service` · Roadmap: Phase 4
> Gated by the single `code_execution` section from `GET /users/me/permissions` (every role gets it — students to solve, `content.author`/`content.review`/`exams.manage` to author and review, `super_admin` for the language catalog).

Five sections, each with its own `api/`, `types.ts`, `pages/`, `components/`, `routes.tsx` (see [src/modules/README.md](../README.md) for the shared layout rules):

- `languages/` — the runtime catalog (`GET /languages` for everyone's editor; `GET /languages/all` + create/edit for `super_admin` only). `LanguageSelect` and `AllowedLanguagesField` are the pickers every other section reuses.
- `runs/` — the standalone online compiler: submit code + stdin, long-poll (`wait=`) until it finishes. `useRunExecution` is the polling hook; `RunOutputPanel` the result view.
- `problems/` — browse, author (create/edit/publish/retire, test cases with reorder, stats), and solve (statement + samples + the in-page workspace: editor, Run, Submit, own submission history). One problem, one status: `draft` (editable) → `published` (frozen — no new draft version, unlike catalog's courses) → `retired`.
- `submissions/` — "My submissions" across every problem, and a submission's own detail (code + per-case verdicts). `useSubmissionExecution` is the submit-and-poll hook, reused by the problem workspace.
- `review/` — every submission across every problem, with the plagiarism signal (`flagged`, `similarity_percent`, and the similar-submission list) for `content.author`/`content.review`/`exams.manage`/`super_admin`. A hidden test case's input/expected/actual never appear here either — `CaseResultOut` only carries them for `is_sample` cases, enforced server-side.

**Review and Languages are narrower than the section itself** (reviewer scopes / `super_admin` only), so neither is a persistent nav item — showing them to everyone with `code_execution` would mean most people click through to a 403. Both are reached instead from the Problems page's own header actions, shown only when the viewer actually has the right scope/role (`ProblemsListPage.tsx`), plus a client-side redirect on `/languages` itself as a second layer.

`shared/ui/CodeEditor.tsx` (plain monospace textarea, Tab-key handling) is a genuine cross-module primitive, not code-execution-specific: ai-interview-service's coding round calls this same service's internal run endpoints, so ai-interview's own frontend module will reuse it later.

**Import:** a problem's test cases can be imported from a JSON list (`POST .../test-cases/bulk`, all or none). **Ask the AI tutor** on the problem workspace and the compiler hands the current code to the tutor (tab-scoped, see `core/lib/storage.ts`). **Not built**: the SSE run stream — long-polling via `wait=` does the same job; and "My submissions" now needs `code.submissions` on the server too.