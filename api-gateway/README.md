# API Gateway

> Status: **Done** · Roadmap phase: **0.5** · Public port: **8000**

The platform's single public entry point. It decides which service a path belongs to, checks a bearer token when one is sent, rate-limits, applies
CORS once, and forwards the request byte-for-byte — no business logic, no database, no background worker.

| | |
|---|---|
| Owns | nothing — stateless; Redis only for rate-limit counters and reading user-management's revocation keys |
| Routes to | every other backend service, by `config/routes.json` (generated from their real, running routes — see below) |
| Never routes | any `.../internal/...` path (service-to-service calls, authenticated by the shared internal token), each service's own `/health`, `/docs`, `/redoc`, `/openapi.json` |

## The rules that shape the design

1. **The route table is generated, not written by hand.** `scripts/generate_routes.py` imports every other service's FastAPI app (from its own
   `.venv`), reads its real OpenAPI paths, and compiles the smallest set of path-prefix rules that sends each one to its own service — refusing to
   compile if two services claim the same path (this caught four real collisions: `/templates` claimed by career-, certificate- and
   notification-service; `/preferences` by job-portal- and notification-service; `/jobs` and `/employers/{id}` by both job-portal-service and
   user-management — each renamed in its owning service to something unambiguous, e.g. student-facing job browsing is `/job-board`,
   user-management keeps `/jobs`/`/employers`). `config/routes.json` and `config/route_inventory.json` (the full path list it was built from) are
   committed; `--check` fails a rebuild if they have drifted from what the services now expose.
2. **Never a path shorter than a resource.** Rules are never coarser than `/api/v1/<segment>`: an unmapped path under a segment that happens to
   belong to only one service today never silently starts routing there once a second service adds something under the same first segment.
3. **The gateway never decides who may do what.** A bearer token, if sent, is checked (signature, expiry, revocation) so a client gets one
   consistent `401` shape everywhere instead of eighteen slightly different ones — but *whether* a token is required, and for what, is entirely each
   service's own `RequireXxx` dependency. No token at all is passed straight through.
4. **A client cannot inject what only the gateway may set.** `X-Internal-Service-Token`, `X-Forwarded-For`, `X-Forwarded-Proto` and `X-Request-ID`
   sent by a caller are dropped and replaced (`app/proxy/headers.py`); a service's own `Server`, CORS and hop-by-hop response headers are stripped
   so the gateway is the only thing that speaks CORS to a browser.
5. **A body is a stream, not a buffer.** Requests and responses are relayed chunk by chunk (`app/proxy/forward.py`) with only a byte-count check
   against `MAX_BODY_BYTES` — a 15 MB spoken interview answer or a certificate PDF passes through exactly like a small JSON call, and a
   server-sent-event stream (`.../stream`) gets a much longer read timeout than an ordinary request.

## Running

```
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
pip install -e ../shared --config-settings editable_mode=compat   # what mypy needs to see lms_common's types
python scripts/generate_routes.py   # needs every other service's own .venv already set up; rewrites config/routes.json
uvicorn app.main:app --port 8000
```

Docker: `docker compose up api-gateway` from `lms-backend/` (no `-migrate`, no `-worker`: this service has neither). `UPSTREAM_URLS` in
`.env.docker` points it at every service's compose name instead of `localhost`.

## Verified

`ruff` and `mypy --strict` clean; **54 tests**, all against fake upstream services (no service is actually run) plus a fakeredis instance:
unit (longest-prefix route matching, a literal beating a wildcard, two services claiming one path is a build-time error, the committed route
table really is what the committed inventory compiles to, every real path of every real service reaches that service and no internal/health/docs
path is reachable, header stripping/rewriting in both directions including repeated `Set-Cookie`, unsafe-path rejection, settings validation
including a malformed `UPSTREAM_URLS`) and integration (every path prefix reaching its service, method/query/an exact byte-for-byte body —
including a webhook's raw signed bytes — arriving unchanged, internal paths refused however they are spelled including percent-encoded traversal,
a service's own health/docs unreachable through the gateway, the internal token and forwarded headers a client sends being dropped and replaced,
CORS applied once and only for an allowed origin, a valid/missing/expired/wrong-key/wrong-type/malformed token, a revoked session/user-version/
organisation via the real Redis access-state keys, per-user and per-IP rate limits kept separate, a tighter limit on `/auth/...`, the forwarded-for
chain only trusted behind `TRUST_PROXY_HEADERS`, an oversized declared and streamed body refused before or during the send, a down service → 502,
a slow one → 504 with unrelated services unaffected, a streamed SSE response and a 1 MiB download passing through intact, liveness/readiness, and
the super-admin-only all-services health view).

**Not exercised:** real Redis (fakeredis), Docker at runtime, a live user-management token round trip, and — because it fronts every other
service — the whole platform actually running behind it at once (each service is still only verified standalone, per its own README).

## Known limits

- **The route table is a build artifact, not live discovery.** Adding an endpoint to a service, or adding a new service, needs
  `scripts/generate_routes.py` run and its output committed before the gateway will route to it — there is no service registry.
- **No circuit breaker, retries or response caching.** A slow or down service is a `502`/`504` to the caller; nothing here retries a request or
  serves a cached answer instead.
- **No per-route rate limit tuning.** One user limit and one anonymous limit apply platform-wide, plus a tighter one for `/api/v1/auth/...`; a
  single expensive endpoint cannot be limited more tightly than the rest without code, not configuration.
- **No WebSocket support.** Every route here is request/response or a streamed HTTP body (SSE); nothing in the platform currently needs a
  WebSocket, so none was built.
