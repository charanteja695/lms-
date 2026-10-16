# AI Gateway

> Status: **Done** · Roadmap phase: **7** · Local port: **8010** · Blueprint: [docs/PRODUCT.md](../../docs/PRODUCT.md) §6

The only service that talks to an LLM provider on the platform's behalf. Every other service that wants a chat
completion, an embedding, or (eventually) speech routes the call through here instead of holding its own provider
key: this is where provider routing and fallback, the prompt registry, per-org quotas and cost, PII redaction,
moderation, tool allow-listing and the audit log all live, once, instead of being reinvented per caller.

| | |
|---|---|
| Owns (own database) | prompts, prompt_versions, org_quotas, org_usage, ai_call_logs, model_routes, org_status_refs (read-model), outbox_events, processed_events |
| Emits events | `ai.usage` |
| Consumes events | `institution.created/activated/suspended` (user-management) |
| API | [docs/API.md](docs/API.md) · [docs/openapi.json](docs/openapi.json) (18 operations) |

Follows the service template in [lms-backend/README.md](../README.md): verifies tokens against user-management's
JWKS for its admin API (never issues its own); its internal API (completions/embeddings/speech) is called by other
services with the shared `INTERNAL_SERVICE_TOKEN` instead, the same scheme assessment-service and
subscription-service use; transactional outbox to `lms:events`; idempotent event consumer (`processed_events`).

## What it does

- **Provider routing and fallback** (`app/providers/`). Claude (Anthropic) is the primary chat provider, Voyage AI
  the embedding provider (Anthropic's recommended partner — it has no first-party embeddings API); each capability's
  fallback order is admin-configurable (`GET`/`PATCH /models`), defaulting to a single entry built from `Settings`.
  A completion tries each configured provider in order; a streaming completion only falls back before its first
  chunk reaches the caller — after that, switching providers mid-stream would mean silently splicing two different
  completions together.
- **Prompt registry** (`app/services/prompt_service.py`). A named prompt (`tutor.explain_concept`) has versions:
  draft → **active** (by someone other than the author) → retired. Every completion renders a specific version's
  template as the system prompt — never a live-edited string — so a call from a month ago replays the same way and
  an eval run compares like with like. The caller always supplies the actual conversation (`messages`) fresh.
- **Guardrails** (`app/guardrails/`), applied in this order, before anything reaches a provider or a log:
  1. a caller-declared tool must be on the prompt version's `allowed_tools` list, or the call is rejected outright;
  2. PII (emails, phone numbers, PAN/Aadhaar-shaped numbers, card-shaped numbers) is regex-redacted from every
     message and the rendered system prompt — the redacted text, never the original, is what's sent upstream *and*
     logged;
  3. the redacted text is checked against a keyword blocklist (`Settings.MODERATION_BLOCKLIST` — a placeholder for
     a real moderation provider behind the same interface); a match blocks the call before any provider is called,
     at no cost, and comes back as a normal `status: "blocked"` result, not an error.
  ai-gateway does not execute tools itself — the caller does, after checking with the student for any write action
  (docs/PRODUCT.md §5.5) — it only enforces which tool *names* a given prompt version may offer the model at all.
- **Quotas and cost** (`app/services/quota_service.py`). An org without an `OrgQuota` row uses the platform
  defaults. Every call **reserves** its estimated token cost under a `SELECT ... FOR UPDATE` row lock and commits
  *before* calling the (slow) provider, then **adjusts** the reservation to the actual usage in a fresh transaction
  afterwards — a failed call is refunded in full. This is the same "reserve, call, adjust; never hold the database
  open across the external call" shape proctoring-service's AI-analyzer integration settled on. Proven under real
  concurrency in `tests/integration/test_postgres.py`.
- **Idempotency** (`app/services/idempotency_service.py`). An `Idempotency-Key` header is cached in **Redis**, not
  Postgres, with a TTL — long enough for a client's retry, without giving a model's output a second, longer-lived
  home merely to satisfy retries.
- **Suspension** (`app/events/consumers/handlers.py`). `institution.suspended` blocks further AI spend for that
  org immediately (`403 ORG_SUSPENDED`); `institution.activated` restores it.
- **Audit/eval log** (`app/models/call_log.py`). One row per call attempt, whatever its outcome — status, provider,
  model, tokens, cost, latency, guardrail flags, and the *redacted* request/response. Pruned after
  `CALL_LOG_RETENTION_DAYS`.

## Events

`ai.usage` `{organization_id, service, user_id, capability, provider, model, prompt_key, prompt_tokens,
completion_tokens, cost_cents, status, call_id, occurred_at}` — for analytics-service (phase 11) and, later,
billing-service. Consumed payloads are documented in `app/events/consumers/handlers.py`.

## Run

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements-dev.txt
cp .env.example .env && alembic upgrade head
uvicorn app.main:app --port 8010          # API
python -m app.worker                      # outbox relay, event consumer, housekeeping
pytest -m "not postgres"                  # 94 tests (SQLite, fakeredis)
pytest -m postgres                        # 2 tests on a real embedded PostgreSQL (pip install pgserver)
```

## Verification (2026-09-22)

**98 tests** — 43 unit (redaction, moderation, tool allow-listing, prompt-template rendering, pricing, provider
fallback, the Anthropic/Voyage HTTP clients against a mocked transport), 51 integration on SQLite, **2 on a real
PostgreSQL** (migration up → down → up with `alembic check` finding no drift; concurrent quota reservations for one
org never spend past the token limit; concurrent first-time reservations for the same org+period don't raise on
the insert race). ruff and `mypy --strict` clean.

### Not built / not verified

- **Not exercised anywhere on this machine:** a real Redis (fakeredis only), and — like Judge0 for code-execution
  and the AI analyzer for proctoring before it — the real Anthropic and Voyage AI HTTP APIs. Both providers'
  clients (`app/providers/anthropic.py`, `app/providers/voyage.py`) are written against their documented request/
  response shapes and tested against a mocked HTTP transport, never the network. Pricing in
  `app/providers/pricing.py` is illustrative, not fetched from either provider's current pricing page.
- **Speech (STT/TTS) is a routing contract only** (`app/providers/speech.py`) — every call answers
  `503 PROVIDER_NOT_CONFIGURED`. Needed first by the phase-10 AI interviewer, not by anything built so far.
- **Moderation is a keyword blocklist**, not a real content-moderation model — a placeholder behind
  `app/guardrails/moderation.py`'s interface.
- **No streaming embeddings**, no batch/offline completion jobs, no per-prompt cost dashboards (usage is queryable
  per org and period, not yet aggregated into a report — that is analytics-service's job, phase 11).
- **Nothing calls this service yet.** ai-tutor-service and support-service (the rest of phase 7) are what will
  actually use the completion/embedding API day to day; until they exist, this is verified against its own
  contract and fake providers, not a real caller's traffic pattern.
