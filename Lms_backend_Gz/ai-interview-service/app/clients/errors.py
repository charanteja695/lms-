"""How a call to another service can fail, in the two ways the caller has to tell apart."""


class Rejected(Exception):
    """The other service refused the request itself (a 4xx): retrying the same request cannot succeed."""

    def __init__(self, message: str, *, status: int, code: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class Unavailable(Exception):
    """A timeout, a connection failure, a 5xx or a rate limit: worth retrying later."""
