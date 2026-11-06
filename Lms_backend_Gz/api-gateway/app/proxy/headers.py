"""Which headers cross the gateway, in each direction. Pure functions, so the rules are testable without a network."""

from collections.abc import Iterable

HOP_BY_HOP = frozenset({"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "trailers", "transfer-encoding", "upgrade"})
# Never accepted from a client: the shared secret services use to call each other, and headers only the gateway may set.
CLIENT_FORBIDDEN = frozenset({"x-internal-service-token", "x-forwarded-for", "x-forwarded-proto", "x-forwarded-host", "x-real-ip", "forwarded", "x-request-id", "host"})
# Never passed back from a service: CORS is applied once, by the gateway; the server banner tells a client nothing it should know.
SERVICE_FORBIDDEN = frozenset({"server", "x-powered-by", "date"})


def request_headers(raw: Iterable[tuple[str, str]], *, client_ip: str, forwarded_for: str | None, scheme: str, request_id: str) -> list[tuple[str, str]]:
    """The headers sent to a service: the client's own (authorization, cookies, content type and length, conditional and range headers...) minus what must not
    cross, plus the gateway's view of who is calling. ``forwarded_for`` is the chain so far, only when the gateway sits behind a proxy it trusts."""
    headers = [(name, value) for name, value in raw if (lower := name.lower()) not in HOP_BY_HOP and lower not in CLIENT_FORBIDDEN]
    chain = f"{forwarded_for}, {client_ip}" if forwarded_for else client_ip
    headers += [("X-Forwarded-For", chain), ("X-Forwarded-Proto", scheme), ("X-Request-ID", request_id)]
    return headers


def response_headers(raw: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """A service's response headers, repeated ones (several ``Set-Cookie``) kept as they are."""
    return [
        (name, value) for name, value in raw if (lower := name.lower()) not in HOP_BY_HOP and lower not in SERVICE_FORBIDDEN and not lower.startswith("access-control-") and lower != "x-request-id"
    ]
