from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Client metadata captured once per request for auditing and rate limiting."""

    ip_address: str | None
    user_agent: str | None
    request_id: str | None
