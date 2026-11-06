# Learning module

> Status: **Done** · Backend: `lms-backend/learning-service` · Roadmap: Phase 3
> Gated by the single `learning` section from `GET /users/me/permissions` (students, institution staff/heads, and admins with the `accounts.manage` scope).

Two sections, each with its own `api/`, `types.ts`, `pages/`, `components/`, `routes.tsx` (see [src/modules/README.md](../README.md) for the shared layout rules):

- `batches/` — a group of one institution's students on one published course version. An institution head (their own institution) or an `accounts.manage` admin (any institution) starts a batch, which reads the institution's entitlement from subscription-service's cache.
- `enrollments/` — enrolling/withdrawing students (each reserves/releases a seat via a synchronous call to subscription-service), and the student-facing pieces: "My learning" (the student's own enrolled courses) and the course player (per-module/topic unlock state, marking items complete).

`common/` holds what both share: the `BatchStatus`/`EnrollmentStatus`/`ItemType` enums (mirroring `learning-service/app/domain/enums.py` and the item types it carries from catalog-service) and their labels/badges/icons.

**The course player only shows what learning-service's API actually returns.** Unlock state is topic/module granular with per-item detail (`topic_id`/`title`/`unlocked`/`completed`/`completed_items`/`required_items` and each item's `completed` flag) — this required a small, additive backend change (see `lms-backend/learning-service/README.md`'s design notes): the service already synced module/topic/item titles from catalog's `course.published` event but never persisted or served them, since unlock-rule computation never needed them; and `Batch` never exposed its own course's id or title, only its immutable `version_id`. Both were added purely for display, with no unlock-rule logic touched.

Batch/enrollment lists have no free-text search, same as subscriptions (learning-service's `ListQuery` only supports `status`) — `BatchFilters`/no dedicated `EnrollmentFilters` component use `FilterSelect` + a clear button, not the shared `FilterBar`.

Institution, course and student names are resolved via the shared id→name cells documented in [src/modules/README.md](../README.md) rule 5 (`InstitutionNameCell`, `CourseTitleCell`, and this session's addition, `UserNameCell` — all three now used by more than one module).

Seat reserve/release itself has no UI: it happens automatically as a side effect of enrol/withdraw (see `lms-backend/subscription-service/README.md`).
