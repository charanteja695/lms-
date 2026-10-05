# AI Gateway API

Base URL `/api/v1` (port 8010). The machine-readable contract is [openapi.json](openapi.json) (18 operations).
Conventions are the platform's ([lms-backend/README.md](../../README.md)): 64-bit ids as strings, success
`{status, code:"SUCCESS", message, <resource>}`, errors `{status:"error", code, message, details[], request_id}`.

## Who may call what

| Caller | Can |
|---|---|
| **Another backend service** (`X-Internal-Service-Token`) | `/internal/*` — completions, embeddings, transcription, speech, on behalf of an org/user it already authenticated itself |
| **Platform AI manager** (`ai.manage` scope) | manage the prompt registry, set any org's quota, see any org's usage and logs, set model routing |
| **Institution staff / head** | see their own institution's quota and usage (not logs, not other orgs') |

There is no end-user-facing part of this API: students and staff never call it directly. See
`app/permissions/policy.py`'s docstring for why the internal half has no per-person policy at all.

## Internal API (`/internal`, `X-Internal-Service-Token`)

- **`POST /internal/completions`** — `{organization_id, service, user_id?, prompt_key, prompt_version?, variables,
  messages, tools?, max_tokens?, temperature?, model_hint?, stream}`. `prompt_key` is mandatory: every call renders
  a registered, versioned template as the system prompt (governance and eval traceability — see
  `app/services/prompt_service.py`); `messages` is the actual conversation, supplied fresh every call. Response
  `{call_id, status: "ok"|"blocked", content, model, provider, prompt_tokens, completion_tokens, cost_cents,
  guardrail_flags, stop_reason}`. `status: "blocked"` (200, not an error) means moderation stopped the call before
  any provider was reached — the guardrail is not something the caller retries around, so it comes back as a normal
  result, not a 4xx. Accepts an `Idempotency-Key` header.
  - `stream: true` instead returns `application/x-ndjson`: one `{"type": "delta", "text": "..."}` line per token,
    then one final `{"type": "usage", call_id, provider, model, prompt_tokens, completion_tokens, cost_cents,
    stop_reason}` or `{"type": "error", code, message}` line. A moderation-blocked streaming request still gets a
    normal (non-streaming) JSON response — nothing has started streaming yet when that decision is made.
- **`POST /internal/embeddings`** — `{organization_id, service, user_id?, texts[], model_hint?}` →
  `{call_id, vectors[][], model, provider, tokens, cost_cents}`. No prompt registry, no moderation (see
  `app/services/embedding_service.py`'s docstring); PII is still redacted from every text first.
- **`POST /internal/transcriptions`**, **`POST /internal/speech`** — the STT/TTS routing contract; always
  `503 PROVIDER_NOT_CONFIGURED` until a provider is wired up (not built — see README "Not built").

**Errors specific to this half:** `404 PROMPT_NOT_FOUND` / `NO_ACTIVE_VERSION`, `422 MISSING_TEMPLATE_VARIABLE` /
`TOOL_NOT_ALLOWED`, `403 ORG_SUSPENDED` / `AI_DISABLED`, `429 REQUEST_QUOTA_EXCEEDED` / `TOKEN_QUOTA_EXCEEDED` /
`BUDGET_QUOTA_EXCEEDED`, `502 PROVIDER_UNAVAILABLE` (every configured provider failed), `503 PROVIDER_NOT_CONFIGURED`.

## Prompt registry (`/prompts`, `ai.manage`)

- `POST /prompts {key, capability, owner_service, description}` — `key` is a dotted slug (`tutor.explain_concept`).
- `GET /prompts`, `GET /prompts/{key}`.
- `POST /prompts/{key}/versions {template, variables[], allowed_tools[], model_params}` — a new **draft**. Every
  `{{placeholder}}` in `template` must be listed in `variables` (`422 UNDECLARED_VARIABLE` otherwise).
- `POST /prompts/{key}/versions/{version}/activate` — makes it the version served when a caller doesn't pin one,
  and retires whatever was active before. Must be called by someone other than the version's author
  (`403 SAME_AUTHOR`) — the same "a second person" discipline certificate-service's template review uses.
- `POST /prompts/{key}/versions/{version}/retire`.

## Quotas and usage (`/orgs/{organization_id}`)

- `GET /quota` / `PUT /quota {monthly_token_limit, monthly_request_limit, monthly_budget_cents, enabled}` — `null`
  a limit to fall back to the platform default (`Settings.DEFAULT_MONTHLY_*`); `enabled: false` is a hard kill
  switch independent of the limits. `GET` is open to the org's own staff/head; `PUT` is `ai.manage` only.
- `GET /usage?period=YYYY-MM` (defaults to the current month) — `{requests_used, prompt_tokens_used,
  completion_tokens_used, cost_cents_used, token_limit, request_limit, budget_cents}`.

## Audit log (`/logs`, `ai.manage`)

`GET /logs?organization_id&service&prompt_key&status&page&per_page` — every call, whatever its outcome.
`request_redacted` and `response_preview` hold only what was actually sent/received *after* redaction; raw PII is
never written here (see `app/guardrails/redact.py`).

## Model routing (`/models`, `ai.manage`)

- `GET /models` → `{chat: [{provider, model}, ...], embedding: [...]}` — the fallback order a completion/embedding
  call tries, in order (`app/providers/router.py`).
- `PATCH /models/{capability} {providers: [{provider, model}, ...]}` — reorder or replace it.

## Events

Emits `ai.usage` per settled call (`{organization_id, service, user_id, capability, provider, model, prompt_key,
prompt_tokens, completion_tokens, cost_cents, status, call_id, occurred_at}`) — for analytics-service and, later,
billing-service. Consumes `institution.created/activated/suspended` from user-management to block AI spend for a
suspended org (`app/events/consumers/handlers.py`).
