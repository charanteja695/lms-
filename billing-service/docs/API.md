# Billing Service API

Base URL `/api/v1` (port 8018). Machine-readable contract: [openapi.json](openapi.json) (28 operations). Platform conventions
([lms-backend/README.md](../../README.md)): bearer token from user-management, ids are 64-bit numbers as strings, success
`{status, code:"SUCCESS", message, <resource>}`, errors `{status:"error", code, message, details[], request_id}`.
**Every amount is an integer number of paise** (1/100 rupee): `118000000` is ₹11,80,000.

## Who may do what

| Caller | Can |
|---|---|
| **Institution head / employer admin** | their own organisation's billing profile, quotes (ask, accept, cancel), issued invoices (never drafts), online payment; an employer admin also buys plans |
| **Billing manager** (`billing.manage`, or super admin) | everything, for any organisation: prices, profiles, discounts, drafts (edit, issue, void), manual payments, credit notes |
| Staff, recruiters, students | no billing |

## Billing profile

The legal name, GSTIN and state a GST invoice needs (user-management does not carry them).
- `GET/PUT /billing-profile` (own organisation) · `GET/PUT /admin/organizations/{org_id}/billing-profile` (billing manager).
  `PUT {legal_name, gstin?, state, address, email?}` — `422 INVALID_GSTIN` for a wrong-shaped GSTIN; `404` for an organisation unknown to this service.

## Prices

- `GET /prices?kind=` — active prices. `GET /admin/prices` — all, inactive too. `POST /admin/prices {kind: course_seat|employer_plan, code, name, unit_amount, job_posts?, valid_days?}`
  (`code` is a course id, or a tier name; a plan needs `job_posts` and `valid_days`; `409 PRICE_EXISTS`). `PATCH /admin/prices/{id} {name?, unit_amount?, active?}` —
  invoices and quotes already made keep the amount they used. A `course_seat` amount is **per seat per 365 days**.

## Quotes

- `POST /quotes {lines: [{course_id, seats, term_days}], organization_id?}` → `201`. Each line = seats × price × term/365 (rounded half up); GST by the profile's state
  (IGST until a profile exists). `422 NO_PRICE` for a course with no price. `GET /quotes`, `GET /quotes/{id}`.
- `POST /quotes/{id}/accept` (`409 QUOTE_NOT_OPEN`, `QUOTE_EXPIRED`) · `POST /quotes/{id}/cancel` · `POST /admin/quotes/{id}/discount {amount, note}` (open quotes only).
  Accepting fixes the price; it does not create a subscription. When subscription-service activates one for the same course and seats, its invoice uses the quoted price
  (and the quote's discount, pro-rata to that line).

## Invoices

- `GET /invoices?status=&organization_id=&page=` — an organisation's issued invoices; a billing manager sees everyone's, drafts included. `GET /invoices/{id}` — the invoice with
  `lines`, `payments`, `credit_notes`, `seller`, the frozen `customer`, `balance_due` and `refund_due`.
- Drafts come from `subscription.activated`. `PUT /admin/invoices/{id} {lines: [{description, quantity, unit_amount}], discount, note}` replaces a draft's lines (`409 INVOICE_NOT_DRAFT`
  once issued). `POST /admin/invoices/{id}/issue` — numbers it `INV/2026-27/000001` (gap-free per financial year), freezes customer and tax split, sets the due date
  (`409 BILLING_PROFILE_MISSING`, `INVOICE_EMPTY`). `POST /admin/invoices/{id}/void {reason}` — unpaid only (`409 INVOICE_NOT_VOIDABLE`); cancels a pending plan.
- Tax: one configured rate. Customer state = seller state → `cgst` + `sgst` (halves; the odd paisa to CGST), otherwise `igst`.
- Statuses: `draft → issued → paid | overdue | void`. `overdue` is set by the worker past `due_date`; an overdue invoice can still be paid.

## Payments

- `POST /admin/invoices/{id}/payments/manual {amount, reference, method?}` — money received outside the platform (bank transfer, cheque, UPI). Always available. Part payments
  allowed; `409 AMOUNT_EXCEEDS_BALANCE`, `INVOICE_NOT_PAYABLE`. The invoice becomes `paid` when payments cover what remains after credit notes.
- `POST /invoices/{id}/payments/gateway {amount?}` → `201 {payment_id, order_id, amount, currency}` — an order with the payment provider (default: everything owed).
  `503 PAYMENT_GATEWAY_NOT_CONFIGURED` with no provider; `503 PAYMENT_GATEWAY_UNAVAILABLE` if it fails. **A contract only** — see the README.
- `POST /webhooks/payment` — the provider's callback (no bearer token): raw body signed HMAC-SHA256 (hex) with `PAYMENT_WEBHOOK_SECRET` in `X-Signature`
  (`401 INVALID_SIGNATURE`). `{event_id, type: payment.captured|payment.failed, order_id, payment_id, amount}`. Always `200 {status, result}` once accepted:
  `paid | failed | rejected` (amount mismatch or invoice no longer payable) `| duplicate | ignored` (unknown order).

## Credit notes

- `POST /admin/invoices/{id}/credit-notes {taxable_amount, reason}` → `201`. Reduces what is owed by the amount plus the tax on it; numbered `CN/2026-27/000001`. The credit notes
  together cannot exceed the invoice's taxable amount (`409 CREDIT_EXCEEDS_INVOICE`); crediting all of it takes the exact remaining tax. Against a paid invoice, `refund_due` shows what to return.

## Employer plans

- `GET /employer/plans/tiers` — plans on sale. `GET /employer/plans` — my company's. `POST /employer/plans/{tier}/purchase` (employer admin) → `201 {plan, invoice}`:
  invoiced and issued at once; `409 BILLING_PROFILE_MISSING`, `PLAN_ALREADY_PENDING`. Paying the invoice activates the plan.

## Events

Emitted (payloads carry `occurred_at`):
`quote.created|accepted|expired {quote_id, organization_id, total_amount, status}` · `invoice.issued {invoice_id, number, organization_id, kind, total_amount, due_date}` ·
`invoice.paid {…, total_amount}` · `invoice.overdue {…, total_amount = still owed}` · `invoice.voided {…, reason}` · `credit_note.issued {credit_note_id, number, invoice_id, organization_id, amount}` ·
`plan.activated {plan_id, employer_id, organization_id, tier, job_posts, ends_at}` · `plan.expired {plan_id, employer_id, organization_id, tier}`.

Consumed: `institution.*`/`employer.*` (a reference to who can be billed) and `subscription.activated {subscription_id, organization_id, course_id, seats_total, ends_at}`.
See `app/events/consumers/handlers.py`.
