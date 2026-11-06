# AI tutor module

> Status: **Done** · Backend: `lms-backend/ai-tutor-service` · Roadmap: Phase 7
> Gated by the single `ai_tutor` section (students, institution staff/heads, `content.author`, `support.manage`, `ai.manage`).

Four sections (see [src/modules/README.md](../README.md) for the layout rules):

- `chat/` — the student's tutor: conversations (learning, tied to an enrolled course, or support), answers **streamed** as they are written (`hooks/useTutorSend`, NDJSON over `fetch`), lesson/FAQ citations with the video moment, hint ladder (hint button when a lesson is open), low-confidence/FAQ/escalation badges, thumbs up/down with an optional reason, "Talk to a person", delete. The tutor's availability (off during a graded test) disables the composer.
- `faq/` — the student's FAQ (`/tutor/faq`) and FAQ management (`/tutor/faqs`): draft, edit, publish, archive. Staff write for their own institution, authors for a course, support managers for any scope; the server scopes the list.
- `insights/` — per course (`/tutor/insights?course=`): feedback totals and unhelpful answers, evaluation sets (questions + the lessons that should answer them, picked from the course's published version; runs with hit rate and MRR), and the search index per version (AI managers reindex).
- `escalations/` — support managers: tutor-to-support hand-offs and re-queueing a failed one.

**Nav:** one "AI tutor" item; `common/pages/TutorHomePage` sends each person to the first screen they can open (`common/hooks/useTutorRights` mirrors the service's `policy.py`), and the staff screens link to each other via `TutorManageActions`.

**Streaming and safety:** each send carries a fresh `Idempotency-Key`. If the streamed request fails or answers with an HTTP error, the hook re-sends the same message through RTK Query with the *same* key — that path refreshes an expired token and shows the server's error, and the key means the message is never stored twice.

**From the course player:** learning's `CoursePlayerPage` shows "Ask the AI tutor" and a per-lesson "Ask" button (route only: `/tutor/chat?course=…&item=…`), so the conversation starts on that course with the lesson as context.

**Backend changes made for this module (ai-tutor-service):** `GET /eval-sets?course_id` (authors had no way to reopen an evaluation set but its id), and `GET /index/status` now also allows `ai.manage` (AI managers could reindex but not see the version ids). Both tested; `docs/API.md` and `openapi.json` updated.

**Promoting a tutor answer to the FAQ** lives in the support module's ticket view (the transcript of a hand-off is the only place staff see tutor message ids). **Code context:** "Ask the AI tutor" on a coding screen attaches the student's code; the chat shows it as a removable chip and sends it as `context.code`/`context.language` with each question.
