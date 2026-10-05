"""Application errors. Every error response shares one JSON envelope (see error_handlers).

Error codes are stable UPPER_SNAKE_CASE strings that clients may branch on; messages are for people.
"""

from typing import Any


class AppError(Exception):
    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    message: str = "Something went wrong on our side. Please try again."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or []
        self.headers = headers
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400
    code = "BAD_REQUEST"
    message = "The request could not be processed."


class AuthenticationError(AppError):
    status_code = 401
    code = "AUTHENTICATION_FAILED"
    message = "Authentication failed."

    def __init__(self, message: str | None = None, **kwargs: Any) -> None:
        kwargs.setdefault("headers", {"WWW-Authenticate": "Bearer"})
        super().__init__(message, **kwargs)


class PermissionDeniedError(AppError):
    status_code = 403
    code = "PERMISSION_DENIED"
    message = "You do not have permission to perform this action."


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "The requested record was not found."


class ConflictError(AppError):
    status_code = 409
    code = "DUPLICATE_DATA"
    message = "A record with the same details already exists."


class ValidationFailedError(AppError):
    status_code = 422
    code = "INVALID_DATA"
    message = "Some fields are missing or invalid."


class RateLimitedError(AppError):
    status_code = 429
    code = "TOO_MANY_REQUESTS"
    message = "Too many requests. Please try again later."

    def __init__(self, retry_after: int, **kwargs: Any) -> None:
        kwargs.setdefault("headers", {"Retry-After": str(max(retry_after, 1))})
        super().__init__(**kwargs)


class QuotaExceededError(AppError):
    status_code = 429
    code = "QUOTA_EXCEEDED"
    message = "This organization's AI usage quota for the current period is exhausted."


class ProviderUnavailableError(AppError):
    status_code = 502
    code = "PROVIDER_UNAVAILABLE"
    message = "The AI provider could not complete the request. Please try again."


class ProviderNotConfiguredError(AppError):
    status_code = 503
    code = "PROVIDER_NOT_CONFIGURED"
    message = "No provider is configured for this capability."
