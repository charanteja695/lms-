"""The gateway end to end, in front of fake services: routing, what is refused, what is stripped, tokens, rate limits, size limits, failures, streaming."""

import json

import httpx
from httpx import ASGITransport, AsyncClient

from tests.conftest import API, ORG, OTHER_KEY, OTHER_USER, SUPER, USER, bearer, make_token


async def test_each_path_reaches_the_service_that_owns_it(client, upstreams):
    expected = {
        f"{API}/tickets": "support-service", f"{API}/employer/plans": "billing-service", f"{API}/employer/jobs": "job-portal-service", f"{API}/employer/interviews": "ai-interview-service",
        f"{API}/jobs": "user-management", f"{API}/job-board": "job-portal-service", f"{API}/certificate-templates": "certificate-service", f"{API}/resume-templates": "career-service",
        f"{API}/notification-preferences": "notification-service", f"{API}/dashboards/hiring": "analytics-service", "/.well-known/jwks.json": "user-management",
    }
    for path, service in expected.items():
        assert (await client.get(path)).status_code == 200
        assert upstreams.last[0] == service and upstreams.last[1].url.path == path, path


async def test_method_query_and_body_reach_the_service_unchanged(client, upstreams):
    body = json.dumps({"name": "Ünïcode ✓", "n": 1}, ensure_ascii=False).encode()
    response = await client.post(f"{API}/tickets?priority=high&q=a+b", content=body, headers={"Content-Type": "application/json", "Idempotency-Key": "abc-12345"})
    assert response.status_code == 200
    service, request, received = upstreams.last
    assert (service, request.method, request.url.query) == ("support-service", "POST", b"priority=high&q=a+b")
    assert received == body and request.headers["idempotency-key"] == "abc-12345" and request.headers["content-type"] == "application/json"


async def test_a_signed_webhook_body_arrives_byte_for_byte(client, upstreams):
    raw = b'{"event_id": "e1",   "type":"payment.captured","order_id":"o"}'  # odd spacing on purpose: re-serialising would break the signature
    await client.post(f"{API}/webhooks/payment", content=raw, headers={"X-Signature": "abc123"})
    service, request, received = upstreams.last
    assert service == "billing-service" and received == raw and request.headers["x-signature"] == "abc123"


async def test_internal_paths_are_never_forwarded_however_they_are_written(client, upstreams):
    for path in (f"{API}/internal/runs", f"{API}/internal/submissions/1", f"{API}/tickets/internal/x", f"{API}/INTERNAL/x"):
        response = await client.get(path)
        assert response.status_code == 404 and response.json()["code"] == "ROUTE_NOT_FOUND", path
    # httpx's own client normalises a literal "/./" or "/../" before the request is even sent (as most real clients do); what a server must
    # still defend against is what does NOT get normalised away: percent-encoded traversal and a doubled slash.
    for path in (f"{API}//internal/runs", f"{API}/tickets/%2e%2e/internal/runs", f"{API}/tickets/..%2finternal/runs"):
        response = await client.get(path)
        assert response.status_code in (400, 404), path
    assert upstreams.requests == []


async def test_a_services_own_health_and_docs_are_not_reachable_through_the_gateway(client, upstreams):
    for path in ("/docs", "/openapi.json", "/redoc", f"{API}/health/live"):
        assert (await client.get(path)).status_code == 404, path
    assert upstreams.requests == []


async def test_an_unknown_path_is_a_404_from_the_gateway_and_never_reaches_a_service(client, upstreams):
    response = await client.get(f"{API}/no-such-thing")
    assert response.status_code == 404 and response.json()["code"] == "ROUTE_NOT_FOUND" and response.json()["request_id"]
    assert (await client.get("/")).status_code == 404
    assert upstreams.requests == []


async def test_the_internal_token_a_client_sends_is_dropped_and_the_gateways_headers_are_set(client, upstreams):
    await client.get(f"{API}/tickets", headers={"X-Internal-Service-Token": "guess", "X-Forwarded-For": "6.6.6.6", "X-Request-ID": "short"})
    headers = upstreams.last[1].headers
    assert "x-internal-service-token" not in headers
    assert headers["x-forwarded-for"] == "127.0.0.1" and headers["x-forwarded-proto"] == "http" and len(headers["x-request-id"]) >= 8 and headers["x-request-id"] != "short"


async def test_a_well_formed_request_id_is_kept_and_returned(client, upstreams):
    response = await client.get(f"{API}/tickets", headers={"X-Request-ID": "req-abcdef123456"})
    assert response.headers["x-request-id"] == "req-abcdef123456" and upstreams.last[1].headers["x-request-id"] == "req-abcdef123456"


async def test_responses_keep_every_cookie_and_lose_the_services_cors_and_banner_headers(client, upstreams):
    def respond(service, request):
        return httpx.Response(
            201, headers=[("Set-Cookie", "refresh=a; HttpOnly"), ("Set-Cookie", "csrf=b"), ("Access-Control-Allow-Origin", "*"), ("Server", "uvicorn"), ("X-Custom", "kept")], json={"ok": True}
        )

    upstreams.responder = respond
    response = await client.post(f"{API}/auth/login", json={"username": "a", "password": "b"})
    assert response.status_code == 201 and response.json() == {"ok": True}
    assert response.headers.get_list("set-cookie") == ["refresh=a; HttpOnly", "csrf=b"] and response.headers["x-custom"] == "kept"
    assert "access-control-allow-origin" not in response.headers and response.headers.get("server") != "uvicorn"
    assert response.headers["cache-control"] == "no-store" and response.headers["x-content-type-options"] == "nosniff"


async def test_a_services_error_status_and_body_pass_through(client, upstreams):
    upstreams.responder = lambda service, request: httpx.Response(409, json={"status": "error", "code": "DUPLICATE_DATA"})
    response = await client.post(f"{API}/tickets", json={})
    assert response.status_code == 409 and response.json()["code"] == "DUPLICATE_DATA"


# ---------------------------------------------------------------- CORS
async def test_cors_is_applied_once_by_the_gateway_for_allowed_origins_only(make_app, upstreams):
    app = make_app(CORS_ORIGINS=["https://app.example"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://gateway.test") as c:
        preflight = await c.options(f"{API}/tickets", headers={"Origin": "https://app.example", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,idempotency-key"})
        assert preflight.status_code == 200 and preflight.headers["access-control-allow-origin"] == "https://app.example" and preflight.headers["access-control-allow-credentials"] == "true"
        assert upstreams.requests == []  # answered by the gateway itself
        actual = await c.get(f"{API}/tickets", headers={"Origin": "https://app.example"})
        assert actual.headers["access-control-allow-origin"] == "https://app.example" and "x-request-id" in actual.headers["access-control-expose-headers"].lower()
        stranger = await c.get(f"{API}/tickets", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in stranger.headers


# ---------------------------------------------------------------- tokens
async def test_a_valid_token_is_checked_and_forwarded_untouched(client, upstreams):
    headers = bearer()
    assert (await client.get(f"{API}/tickets", headers=headers)).status_code == 200
    assert upstreams.last[1].headers["authorization"] == headers["Authorization"]


async def test_no_token_at_all_is_passed_on_for_the_service_to_judge(client, upstreams):
    assert (await client.get(f"{API}/tickets")).status_code == 200
    assert "authorization" not in upstreams.last[1].headers


async def test_a_bad_token_is_refused_at_the_gateway_and_never_forwarded(client, upstreams):
    cases = {
        "expired": {"Authorization": f"Bearer {make_token(expires_in=-3600)}"}, "signed by another key": {"Authorization": f"Bearer {make_token(key=OTHER_KEY)}"},
        "a refresh token": {"Authorization": f"Bearer {make_token(kind='refresh')}"}, "garbage": {"Authorization": "Bearer not.a.jwt"}, "wrong scheme": {"Authorization": "Basic abc"},
        "empty": {"Authorization": "Bearer "},
    }
    for label, headers in cases.items():
        response = await client.get(f"{API}/tickets", headers=headers)
        assert response.status_code == 401, label
        assert response.json()["code"] in {"INVALID_TOKEN", "NOT_AUTHENTICATED"} and response.headers["www-authenticate"] == "Bearer"
    assert upstreams.requests == []


async def test_a_revoked_session_user_version_or_organisation_is_refused(client, upstreams, redis):
    token = make_token(session=1755000000300777, version=3)
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get(f"{API}/tickets", headers=headers)).status_code == 200

    await redis.set("lms:access:session:1755000000300777", "1")
    assert (await client.get(f"{API}/tickets", headers=headers)).json()["code"] == "TOKEN_REVOKED"
    await redis.delete("lms:access:session:1755000000300777")

    await redis.set(f"lms:access:user:{USER}", "4")  # tokens older than version 4 are dead
    assert (await client.get(f"{API}/tickets", headers=headers)).status_code == 401
    assert (await client.get(f"{API}/tickets", headers=bearer(version=4))).status_code == 200
    await redis.delete(f"lms:access:user:{USER}")

    await redis.set(f"lms:access:org:{ORG}", str(2**31))  # everyone in the organisation signed out
    assert (await client.get(f"{API}/tickets", headers=headers)).status_code == 401


# ---------------------------------------------------------------- rate limits
async def test_anonymous_callers_are_limited_per_ip(make_app, upstreams):
    app = make_app(RATE_LIMIT_ANONYMOUS_PER_MINUTE=3)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://gateway.test") as c:
        statuses = [(await c.get(f"{API}/tickets")).status_code for _ in range(5)]
        limited = await c.get(f"{API}/tickets")
    assert statuses == [200, 200, 200, 429, 429] and limited.json()["code"] == "TOO_MANY_REQUESTS" and int(limited.headers["retry-after"]) >= 1
    assert len(upstreams.requests) == 3  # the refused ones never reached a service


async def test_users_are_limited_separately_from_each_other_and_from_anonymous_traffic(make_app, upstreams):
    app = make_app(RATE_LIMIT_USER_PER_MINUTE=2, RATE_LIMIT_ANONYMOUS_PER_MINUTE=100)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://gateway.test") as c:
        mine = bearer(user_id=USER)
        assert [(await c.get(f"{API}/tickets", headers=mine)).status_code for _ in range(3)] == [200, 200, 429]
        assert (await c.get(f"{API}/tickets", headers=bearer(user_id=OTHER_USER))).status_code == 200
        assert (await c.get(f"{API}/tickets")).status_code == 200


async def test_sign_in_paths_have_a_tighter_per_ip_limit(make_app, upstreams):
    app = make_app(RATE_LIMIT_AUTH_PER_MINUTE=2)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://gateway.test") as c:
        assert [(await c.post(f"{API}/auth/login", json={})).status_code for _ in range(3)] == [200, 200, 429]
        assert (await c.get(f"{API}/tickets")).status_code == 200  # other paths are unaffected


async def test_the_client_address_comes_from_the_forwarded_header_only_when_that_is_trusted(make_app, upstreams):
    trusting = make_app(TRUST_PROXY_HEADERS=True, RATE_LIMIT_ANONYMOUS_PER_MINUTE=1)
    async with AsyncClient(transport=ASGITransport(app=trusting), base_url="http://gateway.test") as c:
        assert (await c.get(f"{API}/tickets", headers={"X-Forwarded-For": "203.0.113.5"})).status_code == 200
        assert upstreams.last[1].headers["x-forwarded-for"] == "203.0.113.5, 203.0.113.5" or upstreams.last[1].headers["x-forwarded-for"].startswith("203.0.113.5")
        assert (await c.get(f"{API}/tickets", headers={"X-Forwarded-For": "203.0.113.5"})).status_code == 429  # same caller
        assert (await c.get(f"{API}/tickets", headers={"X-Forwarded-For": "203.0.113.6"})).status_code == 200  # a different one
    naive = make_app(RATE_LIMIT_ANONYMOUS_PER_MINUTE=1)
    async with AsyncClient(transport=ASGITransport(app=naive), base_url="http://gateway.test") as c:
        assert (await c.get(f"{API}/tickets", headers={"X-Forwarded-For": "1.1.1.1"})).status_code == 200
        assert (await c.get(f"{API}/tickets", headers={"X-Forwarded-For": "2.2.2.2"})).status_code == 429  # a spoofed header buys nothing


# ---------------------------------------------------------------- sizes, failures, streaming
async def test_a_declared_oversize_body_is_refused_before_anything_is_sent_on(make_app, upstreams):
    app = make_app(MAX_BODY_BYTES=2048)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://gateway.test") as c:
        assert (await c.post(f"{API}/tickets", content=b"x" * 2048)).status_code == 200
        big = await c.post(f"{API}/tickets", content=b"x" * 2049)
        assert big.status_code == 413 and big.json()["code"] == "PAYLOAD_TOO_LARGE"
        assert (await c.post(f"{API}/tickets", content=b"x", headers={"Content-Length": "abc"})).status_code == 400


async def test_a_body_that_outgrows_its_limit_while_streaming_is_cut_off(make_app, upstreams):
    app = make_app(MAX_BODY_BYTES=2048)

    async def chunks():
        for _ in range(5):
            yield b"y" * 1000

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://gateway.test") as c:
        response = await c.post(f"{API}/tickets", content=chunks())  # no Content-Length: chunked
    assert response.status_code == 413


async def test_a_service_that_is_down_is_a_502_and_one_that_is_slow_a_504_with_the_request_id(client, upstreams):
    upstreams.down.add("support-service")
    down = await client.get(f"{API}/tickets")
    assert down.status_code == 502 and down.json()["code"] == "UPSTREAM_ERROR" and down.json()["request_id"] == down.headers["x-request-id"]
    upstreams.timeout.add("billing-service")
    slow = await client.get(f"{API}/invoices")
    assert slow.status_code == 504 and slow.json()["code"] == "UPSTREAM_TIMEOUT"
    assert (await client.get(f"{API}/certificates")).status_code == 200  # the others are unaffected


async def test_a_streamed_response_passes_through_chunk_by_chunk(client, upstreams):
    async def events():
        for n in range(3):
            yield f"data: {n}\n\n".encode()

    upstreams.responder = lambda service, request: httpx.Response(200, headers={"Content-Type": "text/event-stream"}, content=events())
    async with client.stream("GET", f"{API}/runs/123/stream") as response:
        received = [chunk async for chunk in response.aiter_bytes()]
    assert response.headers["content-type"] == "text/event-stream" and b"".join(received) == b"data: 0\n\ndata: 1\n\ndata: 2\n\n"


async def test_a_large_download_passes_through_intact(client, upstreams):
    payload = bytes(range(256)) * 4096  # 1 MiB
    upstreams.responder = lambda service, request: httpx.Response(200, headers={"Content-Type": "application/pdf", "Content-Disposition": 'attachment; filename="a.pdf"'}, content=payload)
    response = await client.get(f"{API}/certificates/1/pdf")
    assert response.content == payload and response.headers["content-disposition"] == 'attachment; filename="a.pdf"'


# ---------------------------------------------------------------- health
async def test_live_and_ready(client, redis):
    assert (await client.get("/health/live")).json() == {"status": "ok"}
    ready = await client.get("/health/ready")
    assert ready.status_code == 200 and ready.json()["checks"] == {"routes": "ok", "redis": "ok"}


async def test_the_upstream_health_view_is_for_a_super_admin_only(client, upstreams):
    assert (await client.get("/health/upstreams")).status_code == 401
    assert (await client.get("/health/upstreams", headers=bearer(role="student"))).status_code == 403
    ok = await client.get("/health/upstreams", headers=bearer(user_id=SUPER, role="super_admin", org=None))
    assert ok.status_code == 200 and len(ok.json()["services"]) == 18 and set(ok.json()["services"].values()) == {"ok"}

    upstreams.down.add("billing-service")
    degraded = await client.get("/health/upstreams", headers=bearer(user_id=SUPER, role="super_admin", org=None))
    assert degraded.status_code == 503 and degraded.json()["services"]["billing-service"] == "down" and degraded.json()["status"] == "degraded"
