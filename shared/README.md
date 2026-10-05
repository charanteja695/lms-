# lms-common (shared package)

> Status: **Done** (2026-09-18) · Roadmap phase: 0.5, item 11

Code every LMS microservice reuses. It contains **no business logic** — only conventions that
are already fixed across the platform (see `lms-backend/README.md`), extracted from
user-management so the next service doesn't re-implement or drift from them.

| Module | Contents |
|---|---|
| `lms_common.ids` | Public 64-bit id generation and parsing |
| `lms_common.envelopes` | `{status, code, message, ...}` response bases, `PageContext`, `SortOrder` |
| `lms_common.pagination` | `paginate()` (bounded, safe count) and `contains_pattern()` for search |
| `lms_common.auth` | `JWKSVerifier` — verify (never issue) access tokens against user-management's JWKS, with key-rotation-aware caching; `AccessTokenClaims` |
| `lms_common.access_state` | `is_token_revoked()` — read the Redis keys user-management publishes on suspend/delete/role-change/sign-out, within seconds of the change |
| `lms_common.events` | `Event` (the outbox envelope) and `StreamConsumer` — an idempotent consumer group reader for `lms:events` |

## Using it in a new service

```bash
pip install -e ../shared          # or add "-e ../shared" to requirements.txt
```

```python
from lms_common.auth import JWKSVerifier, TokenError
from lms_common.access_state import TokenIdentity, is_token_revoked

verifier = JWKSVerifier(
    issuer="lms-user-management",
    audience="lms",
    fetch_jwks=fetch_user_management_jwks,  # GET /.well-known/jwks.json, your own httpx call
)

async def authenticate(token: str) -> AccessTokenClaims:
    claims = await verifier.verify(token)  # raises TokenError if invalid/expired/unknown key
    identity = TokenIdentity(str(claims.session_id), str(claims.user_id), str(claims.organization_id) if claims.organization_id else None, claims.token_version, claims.issued_at)
    if await is_token_revoked(redis, identity):
        raise TokenError("Access has been revoked")
    return claims
```

Every request should still check, after this: user active in your own data → organisation
active → role/scope allowed → resource in the caller's scope (see `lms-backend/README.md`).

## What's deliberately **not** here

- Request/response schemas for a specific resource (users, courses, ...) — those belong to the
  owning service.
- `FilterQuery`/`ListQuery` and other query-parameter contracts — filters are domain-specific.
- Anything only user-management needs (password hashing, MFA, session issuing) — it is the
  token *issuer*; other services are only ever verifiers.

## Tests

```bash
pip install -e .[dev]
pytest
```

33 tests cover id generation/parsing (strictly increasing within a process, thread-safe), the envelope
shapes, search-pattern escaping, JWKS verification (signing, wrong audience, expiry, unknown key, key
rotation — all with real RSA keys and no network), the access-state reader (session/user/org
revocation, and the no-op case), and the stream consumer (read, ack, idempotent group creation,
redelivery of unacked events after an idle time, rescue of a crashed instance's work, dead-lettering
of poison and malformed events, trimmed entries).

**Stream consumer redelivery.** `StreamConsumer.read()` first reclaims (`XAUTOCLAIM`) events left unacked for
`redeliver_after_ms` (60 s) — whichever consumer name held them — then reads new ones. After `max_deliveries` (10)
failed deliveries an event is copied to `<stream>:dead` (with `group`, `deliveries`, `reason`) and acked. Alert on
that stream's length. Tested against fakeredis only; real Redis semantics (`XAUTOCLAIM` needs Redis ≥ 6.2) are not
exercised on this machine.
