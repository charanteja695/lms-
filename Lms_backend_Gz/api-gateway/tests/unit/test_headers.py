from app.proxy.forward import safe_path
from app.proxy.headers import request_headers, response_headers


def names(headers):
    return [name.lower() for name, _ in headers]


def test_a_client_cannot_send_the_internal_token_or_forge_the_gateways_own_headers():
    sent = [("Authorization", "Bearer x"), ("X-Internal-Service-Token", "secret"), ("X-Forwarded-For", "6.6.6.6"), ("X-Request-ID", "forged"), ("Host", "evil"), ("Cookie", "a=b"), ("Connection", "close")]
    out = request_headers(sent, client_ip="1.2.3.4", forwarded_for=None, scheme="https", request_id="rid12345")
    assert "x-internal-service-token" not in names(out) and "connection" not in names(out) and "host" not in names(out)
    assert ("Authorization", "Bearer x") in out and ("Cookie", "a=b") in out
    assert ("X-Forwarded-For", "1.2.3.4") in out and ("X-Request-ID", "rid12345") in out and ("X-Forwarded-Proto", "https") in out
    assert names(out).count("x-forwarded-for") == 1 and names(out).count("x-request-id") == 1


def test_behind_a_trusted_proxy_the_chain_is_extended_not_replaced():
    out = request_headers([], client_ip="10.0.0.2", forwarded_for="203.0.113.9", scheme="http", request_id="rid12345")
    assert ("X-Forwarded-For", "203.0.113.9, 10.0.0.2") in out


def test_repeated_set_cookie_headers_survive_and_cors_and_banner_headers_do_not():
    upstream = [("Set-Cookie", "a=1"), ("Set-Cookie", "b=2"), ("Access-Control-Allow-Origin", "*"), ("Server", "uvicorn"), ("Transfer-Encoding", "chunked"), ("X-Request-ID", "theirs"), ("Content-Type", "application/json")]
    out = response_headers(upstream)
    assert [v for n, v in out if n == "Set-Cookie"] == ["a=1", "b=2"]
    assert names(out) == ["set-cookie", "set-cookie", "content-type"]


def test_paths_with_dot_empty_or_control_segments_are_not_forwarded():
    assert safe_path("/api/v1/tickets") and safe_path("/api/v1/tickets/") and safe_path("/.well-known/jwks.json")
    for bad in ("/api/v1/../internal", "/api/v1/./x", "/api//v1", "/api/v1/x" + chr(92) + "y", "/api/v1/x\x00", "api/v1"):
        assert not safe_path(bad), bad
