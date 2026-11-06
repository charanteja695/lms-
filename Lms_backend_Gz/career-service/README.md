# Career Service

> Status: **Done** · Roadmap phase: **8** · Local port: **8013** · Blueprint: [docs/PRODUCT.md](../../docs/PRODUCT.md) §5.6

A student's **verified skill profile** and **AI-assisted resume builder**. The platform adds what it can vouch for —
certificates, completed courses, assessment scores — as *verified, read-only* items; the student adds their own education,
experience, projects, skills and achievements, always labelled *self-declared*. Resumes are built from that profile, scored for
how well an applicant tracking system will read them, and exported as PDF or JSON Resume or shared by link.

| | |
|---|---|
| Owns (own database) | profiles, profile_items, attempt_results, resumes, resume_versions, resume_templates; read-models: user_refs, course_refs; outbox_events, processed_events |
| Emits events | `skill_profile.updated` (every profile change, with a revision and counts) · `resume.updated` (version saved, restored, shared, unshared, deleted) |
| Consumes events | `user.*` (user-management) · `course.published` (catalog) · `certificate.issued/revoked` (certificate) · `attempt.finalized` (assessment) |
| Calls | ai-gateway (completions) with the shared internal token |
| API | [docs/API.md](docs/API.md) · [docs/openapi.json](docs/openapi.json) (33 operations) |

## The rule that shapes the design: the AI never invents credentials

1. **Verified items cannot be edited or deleted** by the student (`403 VERIFIED_ITEM_READONLY`); they are created, refreshed and
   deactivated only by event handlers. A revoked certificate leaves the profile at once, and the course with it unless another
   valid certificate covers it.
2. **Self-declared items are labelled** (`label: "Self-declared"`) in the API, the document, and the AI's own input.
3. A resume may give a self-declared item its own wording; on a verified item that is refused.
4. **Every AI answer is a suggestion checked against the facts it was made from** (`app/ai/guard.py`): a number, link, email,
   capitalised name or job-description keyword that appears in the output but not the source is listed in `warnings` and the
   suggestion is `applicable: false`. Nothing from a model is ever saved; the student applies a suggestion by editing.
5. Tailoring never adds a keyword the profile lacks: `keyword-gap` splits the job's terms into *add from your profile* and
   *not in your profile — add only if true*.

## What is where

- **Profile** (`app/services/profile_service.py`, `verified_service.py`). Self-declared kinds are validated per kind
  (`app/schemas/items.py`: `YYYY-MM` dates, end after start, at most 8 bullets, http(s) links). Verified items are keyed by user, kind
  and the source's own id, so redelivered or out-of-order events are harmless (a certificate can arrive before the student or course
  is known; the title is resolved when read). A **skill score** is the best *passed*, released result across topic, module and final
  tests of a course (practice and employer tests never count; an integrity-invalidated attempt is removed and the score recomputed;
  a late older release is ignored). Its **percentile** is computed when read, among students with a passed result for that course,
  and only shown once `PERCENTILE_MIN_COHORT` (20) students have one: a percentile among a handful of people is noise.
- **Resumes** (`app/services/resume_service.py`, `app/resume/document.py`). A *draft* is an ordered list of sections, each an ordered
  list of references to profile items. The *document* resolves the draft against the profile at one moment; a **version** freezes the
  draft and that document with its ATS score, so old versions keep showing what they showed. Edits carry `expected_revision`
  (`409 STALE_DRAFT` for a lost race, proven under real concurrency). Restoring saves the current draft as a version first. Keep one
  resume per target role; `duplicate` copies one. Each resume has an **experience level** (`fresher`, `junior` 1–3 yrs, `mid` 3–8,
  `senior` 8+): it sets the section order of a new draft (a fresher leads with skills, projects and internships; experienced people
  with work history, education last), changing it reorders an existing draft (nothing is shown or hidden), and the ATS length target
  follows it. `GET /resume-options` serves the levels (with what each changes), ways to start, AI tones, share-expiry choices and role
  suggestions — the student's own target roles first, then `RESUME_ROLE_SUGGESTIONS` — so the client hardcodes none of them.
- **Import** (`app/importing/`, `POST /profile/import`): an old resume or a LinkedIn "Save to PDF" (PDF, .docx or .txt, up to
  `MAX_IMPORT_BYTES`; read, never stored; the file type is decided by its bytes; PDFs read for at most 10 pages, a .docx with a DTD or
  entity declaration is refused). The `career.import` prompt reads the text into entries; each entry is kept only if it is a valid
  profile item **and** copied from the file — no number, link or capitalised word (a company, school, tool) that the file lacks.
  Nothing is saved: the student picks entries and sends them to `POST /profile/items/bulk` (all-or-nothing).
- **Templates** (`app/rendering/templates.py`): Classic, Modern, Compact — all single-column plain text with standard headings, the
  layout an ATS reads in order. `ats_safe` is a property of the template; a template that breaks the rule lowers the score.
- **ATS score** (`app/ats/`): rule-based, so the same resume always scores the same and each point has a reason. Contact 10 ·
  sections 15 · bullet quality 30 (action verb, a number, length, wording) · summary 5 · length 10 · template 10 · keyword match 20
  (only with a job description; otherwise scaled to the 80 that apply). `fixes` are ordered most valuable first and point at the
  section and item; `path_to_100` lists each part short of full marks with the points (out of 100) it would add and its fixes.
  **It is a quality heuristic, not calibrated against any real ATS.**
- **AI** (`app/services/ai_service.py`, prompts in `app/ai/prompts.py`): summary, bullet rewrite, tailored summary, grammar polish.
  Prompts are registered as drafts with `python -m app.cli register-prompts` and must be activated by a *different* AI manager in
  ai-gateway. The grammar and tone check itself (repeated words, first person, weak openings, filler) is rule-based and free.
  No transaction is held open across a model call; gateway quota/disabled/unavailable become `429 QUOTA_EXCEEDED`,
  `403 AI_DISABLED`, `503 AI_UNAVAILABLE`, moderation-blocked text `422 AI_CONTENT_BLOCKED`.
- **Export and sharing** (`app/rendering/`): PDF (server-rendered with reportlab, real text), JSON Resume, and a public link. A link is
  pinned to one saved version (edits afterwards change nothing), hides contact details unless asked, expires (30 days by default),
  is replaced when you share again, dies when you revoke or delete the resume, and answers one and the same `404` whether unknown,
  revoked or expired. Public pages send `noindex` and are rate limited per address.

## Running

```
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
pip install -e ../shared --config-settings editable_mode=compat   # what mypy needs to see lms_common's types
alembic upgrade head && uvicorn app.main:app --port 8013
python -m app.worker                                               # outbox relay, event consumer, housekeeping
```

Docker: `docker compose up career-service-migrate career-service career-service-worker` from `lms-backend/`.

## Verified

`ruff` and `mypy --strict` clean; **71 tests**: unit (the invention guard, keyword gap, language rules, document building, ATS
scoring, PDF and JSON Resume rendering) and integration over SQLite (profile and verified items from events incl. redelivery and
revocation, skill scores and percentile, resumes, validation, stale edits, versions and restore, pruning, ATS, keyword gap,
grammar, every AI path incl. invented facts and gateway failures, exports, share links, expiry, rate limit), plus PostgreSQL
through an embedded server (`pgserver`): migration up→down→up with no drift from the models; the whole flow; six racing edits →
one winner; eight simultaneous version saves numbered 1..8; five concurrent duplicate certificate events → one certificate.

**Not exercised:** real Redis (fakeredis in tests), Docker at runtime, a live user-management token round trip, the real
Anthropic API (ai-gateway is mocked at its HTTP contract — so prompt quality is unjudged), the running worker loop against a
live stream, opening the PDFs in a viewer or an actual ATS (they are checked for validity and size, not looked at).

## Known limits

- **PDF fonts are Latin only.** Other scripts (e.g. Devanagari) print as `?`; the response header `X-Unrenderable-Characters` says
  how many. JSON Resume and the share JSON keep Unicode. A font bundle is the next step.
- **Education, experience and projects are self-declared.** Nothing emits verified education or project submissions yet (there is
  no such service), so the only verified items are certificates, completed courses and assessment scores. Skill scores are
  per course, not per skill tag (the assessment events carry no tags).
- A course's title shows as "Course" until its `course.published` event has been seen.
- JSON Resume dates are read from the *current* profile, so a version exported after its item was deleted has no dates.
- No LinkedIn share button, no embedding-based similarity (the keyword match is exact on normalised words), no notifications.
- `attempt.graded` is deliberately not consumed: a skill score must come from a *released* result.
