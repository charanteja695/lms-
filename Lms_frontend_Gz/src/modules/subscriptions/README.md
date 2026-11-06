# Subscriptions module

> Status: **Done** · Backend: `lms-backend/subscription-service` · Roadmap: Phase 2
> Gated by the single `subscriptions` section from `GET /users/me/permissions` (institution heads, and admins with the `accounts.manage` scope).

Two sections, each with its own `api/`, `types.ts`, `pages/`, `components/`, `routes.tsx` (see [src/modules/README.md](../README.md) for the shared layout rules):

- `course-requests/` — an institution head requests seats on a published course for their own institution; an `accounts.manage` admin approves (creating the subscription, optionally overriding seats/term) or rejects (with a reason).
- `subscriptions/` — the resulting course × institution entitlement: seats used/total, term dates, and cancellation.

`common/` holds what both share: the `CourseRequestStatus`/`SubscriptionStatus` enums (mirroring `subscription-service/app/domain/enums.py`) and their labels/badges.

subscription-service's own API returns only `organization_id`/`course_id` on every request and subscription — never a name, since it only keeps a local id-only cache of the institutions/courses it references. Names are resolved for display via `user-management/common/components/InstitutionNameCell.tsx` and `catalog/common/components/CourseTitleCell.tsx` — the one documented cross-module exception (see [src/modules/README.md](../README.md) rule 5), shared with the `learning` module for the same reason.

No free-text search on either list: `subscription-service`'s `ListQuery` only supports a `status` filter, so neither list page uses the shared `FilterBar` (which assumes a search box) — just `FilterSelect` + a clear button.

The seat reserve/release endpoints are service-to-service calls (learning-service reserving/releasing a seat on enrol/withdraw) and have no UI here.
