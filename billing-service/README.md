# Billing Service

> Status: **Done** · Roadmap phase: **11** · Local port: **8018** · Blueprint: [docs/PRODUCT.md](../../docs/PRODUCT.md) §5.10

Quotes, GST invoices, payments and credit notes for institution subscriptions, and job-post plans for employers. It never decides
what an organisation is *entitled* to — subscription-service and job-portal-service do, from the events this service emits. **The
payment gateway is a contract only** (D13): manual payments (a bank transfer or cheque an admin records) always work.

| | |
|---|---|
| Owns (own database) | price_items, billing_profiles, quotes, invoices, invoice_lines, number_counters, payments, gateway_events, credit_notes, org_plans; read-model: org_refs; outbox_events, processed_events |
| Emits events | `quote.created/accepted/expired` · `invoice.issued/paid/overdue/voided` (`total_amount` in paise) · `credit_note.issued` (`amount`) · `plan.activated/expired` (`employer_id`, `tier`, `job_posts`) |
| Consumes events | `institution.*`, `employer.*` (user-management: who can be billed) · `subscription.activated` (subscription-service: drafts the institution's invoice) |
| Calls | a payment provider's order API — contract only, never exercised against a real one |
| API | [docs/API.md](docs/API.md) · [docs/openapi.json](docs/openapi.json) (28 operations) |

## The rules that shape the design

1. **Money is an integer number of paise, everywhere.** No float touches an amount (`app/billing/tax.py`): the CGST, SGST/IGST and the total
   always add up to the paisa, and a credit note that clears an invoice takes the exact remaining tax rather than a rounded share of it.
2. **An issued invoice never changes.** A draft is system-generated and editable; issuing numbers it, freezes the customer's details and the
   tax split, and from then on the only correction is a **credit note** (its own number, its own document). Voiding is only for an unpaid invoice.
3. **Numbers are gap-free per financial year (April–March)**, taken under a row lock on a per-series counter, so ten invoices issued at once get
   ten distinct consecutive numbers — proven on real PostgreSQL, not assumed.
4. **The tax state comes from a billing profile this service owns.** user-management's organisation events carry no state, and a GST invoice
   needs one (in-state → CGST+SGST, otherwise IGST), so each organisation (or a billing manager for it) sets a **billing profile** — legal
   name, GSTIN (shape-checked only), state, address. Issuing without one is refused (`BILLING_PROFILE_MISSING`).
5. **The payment gateway is a contract, and manual payments never depend on it.** `app/gateways/payment.py` speaks a typical order/webhook API,
   verified only against a mocked transport. With no `PAYMENT_GATEWAY_URL`, online payment answers `503 PAYMENT_GATEWAY_NOT_CONFIGURED` and an
   admin records the money instead. The webhook is HMAC-SHA256 signed, de-duplicated by event id, and applied under the invoice's lock.
6. **Billing is never asked at request time.** A plan's activation and expiry are events; job-portal-service keeps its own read-model of who may post.

## What is where

- **Prices** (`price_service.py`): a per-seat, per-365-days price for a course, or an employer plan tier (`job_posts`, `valid_days`). Changing a
  price never touches a quote or invoice already made — they froze the amount they used.
- **Quotes** (`quote_service.py`): an institution head asks for course × seats × term; the price list prices it (pro-rated by term), GST uses the
  profile's state (IGST until one is set), a billing manager may discount it, the head accepts within `QUOTE_VALID_DAYS`. An accepted quote fixes the
  price the matching subscription's invoice will use (same course, same seats), even if the list price has since moved.
- **Invoices** (`invoice_service.py`, `app/events/consumers/handlers.py`): `subscription.activated` drafts one, idempotently per subscription. A
  course with no price drafts a zero invoice with a note ("No price configured"), which cannot be issued until a billing manager sets the lines.
  A customer never sees a draft.
- **Payments** (`payment_service.py`): manual (any amount up to the balance, part payments allowed) or through the gateway; the invoice is paid when
  payments cover what remains after credit notes, and a credit note against a paid invoice shows as `refund_due` (the money movement is manual).
- **Employer plans** (`plan_service.py`): an employer admin buys a tier (needs a profile); it is invoiced at once; paying the invoice activates it and
  emits `plan.activated`; the worker ends it at its term (`plan.expired`). Voiding the invoice cancels the pending plan.
- **Worker** (`app/worker/runner.py`): outbox relay, `lms:events` consumer, and sweeps — invoices past due → `overdue`, stale quotes → `expired`,
  plans past their term → `expired`, each announced exactly once (rows locked with `SKIP LOCKED`).

## Running

```
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
pip install -e ../shared --config-settings editable_mode=compat   # what mypy needs to see lms_common's types
alembic upgrade head && uvicorn app.main:app --port 8018
python -m app.worker        # outbox relay, event consumer, overdue/quote/plan sweeps, housekeeping
```

Docker: `docker compose up billing-service-migrate billing-service billing-service-worker` from `lms-backend/`. Set `SELLER_LEGAL_NAME`, `SELLER_GSTIN`,
`SELLER_STATE`, `GST_RATE_PERCENT` and `PAYMENT_WEBHOOK_SECRET` (staging/production refuse the development secret).

## Verified

`ruff` and `mypy --strict` clean; **56 tests**: unit (financial year boundaries, pro-rating, the GST split and its odd paisa, "the parts always add up",
state comparison, discount clamping, GSTIN shape) and integration over SQLite (profiles and who may set whose, the price list, quotes with GST by state,
discounts, accept-once, expiry; drafting from `subscription.activated`, idempotency, an accepted quote's price and discount carrying over after the list
price changed, an unpriced course, drafts hidden from customers, numbered issue, IGST for out-of-state, profile required, sequential numbers, issued
invoices immutable, only billing managers edit/issue/void, void, the exact fields analytics reads; part and full manual payments, overpayment and
zero refused, gateway order + signed webhook + replay, forged/unsigned webhook, failed and mismatched payments, unknown order acknowledged, gateway
unconfigured → 503 with manual still working, provider outage → 503 and no stray payment; credit notes with their own numbers, a whole-invoice credit
leaving no rounding remainder, over-credit refused, `refund_due` on a paid invoice; plan purchase → invoice → payment → `plan.activated`, profile
required, one pending plan at a time, role checks, void cancels the plan, expiry announced once), plus PostgreSQL through an embedded server
(`pgserver`): migration up→down→up with no drift, **ten invoices issued at once → numbers 1..10 exactly**, **one webhook delivered five times → paid
once**, and two payments racing for one balance → one accepted.

**Not exercised:** a real payment gateway (contract only, mocked), real Redis (fakeredis), Docker at runtime, a live user-management token round trip,
and subscription-service's real HTTP (the event is exercised with its documented payload).

## Known limits

- **No invoice PDF.** An invoice is the JSON document (with everything a GST invoice prints); rendering it to PDF was not built.
- **One GST rate, not a tax engine.** `GST_RATE_PERCENT` applies to every line; CGST+SGST vs IGST is decided by comparing the customer's profile state
  to `SELLER_STATE`. No cess, reverse charge, TDS, e-invoicing (IRN) or e-way bill; GSTINs are checked for shape, never against the GST portal.
- **A refund is a record, not a payout.** A credit note against a paid invoice reports `refund_due`; the gateway's refund call is not built.
- **Money is INR only.** `currency` is stored on each invoice, but every price, tax and total assumes rupees.
- **A plan does not stack or renew.** Buying a second tier while one is active makes a second plan; job-portal-service decides what that means.
  There is no auto-renewal and no dunning beyond the `overdue` flag and its event.
- **Only `subscription.activated` is consumed for institutions.** A subscription that is cancelled or expires does not auto-credit its invoice; a billing
  manager issues the credit note. `course_request.decided` and `subscription.changed` (named in an earlier sketch) are not used: the first carries no price,
  and no service emits the second.
- **The organisation's billing profile must be set by a person.** Nothing in the events carries a state or GSTIN.
