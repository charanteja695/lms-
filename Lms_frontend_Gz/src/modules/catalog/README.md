# Catalog module

> Status: **Done** · Backend: `lms-backend/catalog-service` · Roadmap: Phase 1
> Gated by the single `catalog` section from `GET /users/me/permissions`.

Two sections, each with its own `api/`, `types.ts`, `pages/`, `components/`, `form/`, `hooks/`, `routes.tsx` (see [src/modules/README.md](../README.md) for the shared layout rules):

- `courses/` — course CRUD, and the version authoring lifecycle: rules, modules → topics → items (add/edit/delete/reorder), submit → approve/reject → publish → retire, and the review-history timeline. Curriculum editing is only possible on a `draft` version; the tree renders read-only once submitted.
- `learning-paths/` — learning path CRUD, adding/removing/reordering member courses, and publish/archive.

`common/` holds what both share: the `ContentStatus`/`ItemType`/`UnlockMode` enums (mirroring `catalog-service/app/domain/enums.py`), their labels/badge, and `ContentStatusBadge`.

Curriculum reordering uses up/down buttons, not drag-and-drop (no drag library in this app). Media (video clips, transcripts) is authored in `media-service`; this module only records a `media_id` and shows `media_ready`/`transcript_ready` flags — it does not upload or play media itself.

Action visibility follows the same rule as every other module: buttons are shown only when the signed-in person's `content.author`/`content.review` admin scope and the record's own status allow the action, but the backend is what actually enforces it — the UI is a convenience, not the authority.
