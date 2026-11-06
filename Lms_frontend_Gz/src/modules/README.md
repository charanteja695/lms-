# Modules

There is one folder per **management**, matching a backend service. Each module is split into **sections**, and each section is made of small, single-purpose files.

```
modules/<management>/
├── routes.tsx            combines the section routes of this module
├── navigation.ts         side-menu items this module adds
├── common/               shared by the sections of this module only (types, labels, badges, pickers)
└── <section>/
    ├── api/              RTK Query endpoints (the only place that calls the backend)
    ├── types.ts          request/response types, mirroring the service's docs/API.md
    ├── pages/            one screen per file (lazy-loaded from routes.tsx)
    ├── components/       pieces of those screens, grouped by screen: list/, detail/, form/ ...
    ├── hooks/            section hooks (actions menus, error handling)
    ├── form/             form value types + mapping to/from API bodies
    └── routes.tsx        URL → page for this section
```

## Rules

1. **No business logic in the frontend.** Rules, permissions, validation and calculations belong to the backend. What a person may do comes from `GET /users/me/permissions` (`permissions`, `sections`, `menu`): read it with `user-management/common/permissions/useCan` — `can(key)` for a management permission (a super admin holds all), `holds(key)` for a person's own participation — never from `role` or `scopes`. Screens send what the user entered and show the server's result. A server error for a field (`details[].field`) is shown on that field.
2. **API calls only through `api/`.** Pages and components use the generated hooks. Tag invalidation keeps lists and details fresh, so there is no manual refetching.
3. **Reuse before you write.** Use `@/shared/ui` (Button, Card, DataTable, FilterBar, Modal, ...) and `@/shared/form` (TextField, SelectField, ...). Anything generic goes there, not into a module.
4. **Small files.** When a file grows past ~150 lines, split it: columns → `components/list/useXColumns.tsx`, filters → `components/list/XFilters.tsx`, detail cards → `components/detail/*Card.tsx`, form sections → `components/form/*Section.tsx`.
5. **Modules do not reach into each other's internals**, with two exceptions: `user-management/auth` (the current user and guards) and `user-management/common/types` are used across modules; and any module may read (never write) an id→display-name resolver hook/cell that lives in `common/` of the module owning that data — e.g. `user-management/common`'s `useInstitutionName`/`InstitutionNameCell` and `useUserName`/`UserNameCell`, or `catalog/common`'s `useCourseTitle`/`CourseTitleCell`. Several other services (subscription-service, learning-service, ...) return only an id, never a name, because each keeps just a local id-only cache of what it references — resolving one for display is not business logic, but it is still the one place these modules cross a boundary, so a new resolver stays narrow (one id in, one name out) and lives with the data it resolves, not with whichever module first needed it.
6. **Add a module** by creating its `routes.tsx` and `navigation.ts`, then registering them in `src/app/router.tsx` and `src/app/navigation.ts`.

| Module | Status |
|---|---|
| `user-management/` (auth, account, users, admins, institutions, downloads, roles & permissions) | Done |
| `dashboard/` (home: today's courses and tests, a workspace card per screen, admin counts) | Done |
| `catalog/` (courses, authoring lifecycle, learning paths) | Done |
| `subscriptions/` (course requests, subscriptions) | Done |
| `learning/` (batches, enrolments, course player) | Done |
| `code-execution/` (compiler, problems, submissions, review, languages) | Done |
| `assessments/` (question bank, tests, attempts, grading) | Done |
| `proctoring/` (pre-check, live monitoring, integrity cases, in-exam client) | Done |
| `certificates/` (issued certificates, templates, public verification) | Done |
| `ai-tutor/` (streaming tutor chat, FAQ, course insights, escalations) | Done |
| `support/` (student tickets, agent queue, SLA report, canned replies, SLA policies) | Done |
| `career/` (skill profile, resume builder with ATS/AI/versions/sharing, public resume) | Done |
| `job-portal/` (job board, applications, employer jobs & pipeline, drives, placements, review) | Done |
| `ai-interview/` (practice & screening interviews, plans, calibration, reviews, appeals) | Done |
| `notifications/` (header bell, inbox, email preferences, templates, deliveries) | Done |
| `analytics/` (role-scoped dashboards, organisation filters, scheduled reports) | Done |
| `billing/` (invoices, quotes, hiring plans, prices, billing profiles) | Done |
| `ai-settings/` (AI usage and limits per organisation, model routing, prompt versions, request log) | Done |

## Sidebar groups

`app/navigation.ts` `NAV_GROUPS`: **Learn** (my learning, courses, learning paths, batches, AI tutor) · **Practice**
(coding practice, compiler, submissions) · **Exams** (my tests, question bank, tests, attempts, grading, proctoring,
exam reviews, certificates) · **Careers** (career, jobs, AI interviews) · **People** (my organisation, institutions,
employers, users, admins) · **Business** (course requests, subscriptions, billing, analytics) · **Administration**
(roles & permissions, AI settings, audit log, downloads) · **Help** (support). Each module sets its entries' `group`.
A heading shows only when the person has something under it; the home page groups its cards the same way.
Ctrl/Cmd+K (`shared/layout/QuickJump`) jumps to any of the person's pages by name.
