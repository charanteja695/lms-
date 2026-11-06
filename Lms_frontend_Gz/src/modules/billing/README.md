# Billing module

> Status: **Done** · Backend: `lms-backend/billing-service` · Roadmap: Phase 12
> Gated by the `billing` section (institution heads, employer admins, `billing.manage`). Every amount is paise; `common/format.ts`'s `inr` shows it, `toPaise` converts form input.

One nav item, **Billing**. `common/pages/BillingHomePage` opens Plans for an employer admin and Invoices for everyone else. `common/hooks/useBillingRights` mirrors `policy.py`, and `BillingActions` links the pages each person may use.

- `invoices/`:
  - **Contacts** see their organisation's issued invoices and can pay the balance online. The service only creates the provider order (its README: "a contract only").
  - **Billing managers** see every invoice, drafts included, and can filter by organisation (`common/components/OrgFilter`, through the user-management directory).
  - **Invoice page:** the seller and the frozen customer, lines, the GST split, credited and paid amounts, balance and any refund due, payments and credit notes.
  - **Manager actions,** shown by invoice state: edit a draft, issue, void (unpaid only), record a manual payment, issue a credit note, and open the organisation's billing profile.
- `quotes/`:
  - **Heads** ask for course-seat quotes (only priced courses are offered), then accept or cancel them.
  - **Managers** also quote for an organisation and discount open quotes.
  - **Totals** come from the server.
- `plans/`: an employer admin buys a hiring plan. Its invoice is issued at once, and the plan starts when the invoice is paid.
- `prices/` (managers): course-seat and employer-plan prices. Create one (a course from the catalog picker, or a tier code), rename it, change the amount, or take it off sale.
- `profile/`: the legal name, GSTIN, state and address a GST invoice needs. A contact edits their own; a manager edits any organisation's.

**Backend changes (billing-service), tested** *(the test suite now has 58 tests)*:
- `GET /quotes` accepts `organization_id` for billing managers. It was always `None`, though `/invoices` already filtered.
- Course quotes for a company are refused with `409 NOT_AN_INSTITUTION`, because course seats are subscribed by institutions only.
