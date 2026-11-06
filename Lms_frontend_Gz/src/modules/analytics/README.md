# Analytics module

> Status: **Done** · Backend: `lms-backend/analytics-service` · Roadmap: Phase 11
> Gated by the `analytics` section (institution staff and heads, employer members, and platform admins with a domain scope or `analytics.view`).

One nav item, **Analytics**, which shows the first dashboard this person may open; a tab switches between the others. `common/hooks/useAnalyticsRights` mirrors `check_dashboard_access` in analytics-service:
- **Platform admins** see each platform-wide dashboard their scope unlocks (`analytics.view` unlocks all). They can filter by institution (required for the Institution dashboard) and, on Hiring, by company. Both pickers use user-management's names-only directory.
- **Members** see only their own organisation:
  - institution head and staff: Institution, plus Hiring for their own students;
  - employer: Hiring for their company's jobs.
  Their own id is always sent explicitly.

- `dashboards/`:
  - **Layout:** `common/dashboards.ts` holds each dashboard's tiles and breakdowns. The numbers come from the server.
  - **Formatting (`metricValue`):** rates are fractions, billing amounts are paise, CTC is whole rupees, and AI cost is US cents.
  - **Breakdowns:** one-hue bars, largest first. Labels and values are shown as text, and each bar has a hover tooltip.
  - **Period:** 7, 30 or 90 days.
- `reports/`: the person's own scheduled reports. You can create one (dashboard, filters, frequency, format), run it now or stop it; ready runs can be downloaded through the authenticated `downloadFile`.

**Backend changes, tested:**
- **analytics-service:** an institution's head and staff can now read `/dashboards/hiring?organization_id=<their own>`. The docs promised this, but only platform scopes could. *(The test suite now has 27 tests.)*
- **user-management:** new `GET /directory/organizations[/{id}]`, a names-only lookup for any admin or super admin, because `/institutions` and `/employers` list only what an admin owns. On the frontend, `common/api/directoryApi.ts`, `useAnyInstitutionOptions` / `useAnyEmployerOptions` and `OrganizationNameCell` use it.
- **Frontend types:** `AdminScope` now includes `analytics.view` and `billing.manage`, as the backend does.
