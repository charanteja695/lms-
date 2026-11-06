# Support module

> Status: **Done** · Backend: `lms-backend/support-service` · Roadmap: Phase 7
> Gated by the single `support` section (students; institution staff/heads; `exams.manage` and `support.manage` admins).

Sections (see [src/modules/README.md](../README.md) for the layout rules):

- `tickets/` — the student's side: open a ticket (category decides the queue; optional course from `learning/common`'s `useListMyCoursesQuery`; an `Idempotency-Key` per form), follow the public conversation, reply (reopens a resolved ticket within the window), close, rate 1–5 once resolved.
- `agent/` — the queue (per-queue summary tiles, filters, most urgent first) and a ticket: conversation with internal notes, reply or internal note with canned replies filled in server-side and "then waiting / resolved", claim / assign (the server's own list of eligible people) / release / resolve / reopen / close, priority and category, SLA due times, the audit trail, and — for a ticket the AI tutor handed off — the tutor conversation, where staff and support managers can add a good tutor answer to the tutor FAQ as a draft.
- `reports/` — SLA compliance over the agent's queues for a date range.
- `config/` — canned replies (managers platform-wide, institution staff their institution's) and SLA policies (support managers).

`common/` holds the enums, labels, badges, `MessageThread`, attachments (`useAttachmentUploads` uploads each picked file straight to storage; `AttachmentPicker` on a new ticket and both reply boxes; `MessageAttachments` opens a fresh short-lived link per click) and `useSupportRights` (mirrors support-service's `policy.py`). One "Support" nav item; `SupportHomePage` sends students to their tickets and agents to the queue.

**Backend changes made for this module:**
- support-service: attachments on messages (`POST /attachments/upload-url`, `attachments` on tickets and replies, download links per message, own S3 bucket).
- support-service: `GET /agent/tickets/{id}/transcript` (support-service reads the tutor conversation from ai-tutor-service's internal API once it has decided the agent may handle the ticket — documented in ai-tutor but never wired), `source_ref` on tickets, and `GET /agent/tickets/{id}/assignees` (who `/assign` would accept; a support manager could not list admins anywhere). Tested; docs and OpenAPI updated.
- user-management: admins no longer all get the `support` section — support-service only lets `support.manage` / `exams.manage` admins act as agents, so the blanket entry was a section of 403s.

The FAQ promotion calls ai-tutor-service through this module's own `agent/api/promoteApi.ts` (rule 5).

**Live updates:** an open ticket and the ticket lists re-check every `VITE_LIVE_REFRESH_SECONDS` while the tab is focused. **Not built:** attachments (support-service has none).