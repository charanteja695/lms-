# Notifications module

> Status: **Done** · Backend: `lms-backend/notification-service` · Roadmap: Phase 3
> Gated by the `notifications` section (every member role and every admin: everyone has an inbox).

No side-nav item: the entry point is the **header bell** (`inbox/components/NotificationBell.tsx`, mounted by `shared/layout/AppLayout`), which shows the unread count and re-checks it every `VITE_NOTIFICATION_POLL_SECONDS` while the tab is focused.

- `inbox/`: all / unread tabs, mark one or all read. "Open …" links each category to the module that owns it (`common/categoryLinks.ts`), and only when that section is open to the person.
- `preferences/`: per category, whether it is also emailed. A category the server marks not editable is always emailed, and its toggle is disabled.
- `admin/` (super admin only; the service enforces it):
  - **Templates:** each notification's wording per channel, with its fixed placeholders. Reset returns a template to the default.
  - **Email deliveries:** filtered by status; a failed delivery can be retried.

**Backend change (user-management):** the `notifications` row in `_MODULE_ACCESS` now includes `admin`. Every admin has an inbox whatever their scopes; until now only super admins could open it. Tested.
