"""OpenAPI documentation for error responses, so every endpoint lists what can go wrong."""

from typing import Any

from lms_common.envelopes import ErrorResponse


def _error(description: str, code: str, message: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {
            "application/json": {
                "example": {
                    "status": "error",
                    "code": code,
                    "message": message,
                    "details": details or [],
                    "request_id": "5f0c2b9ad4e84d6c9d1f3a7e2b8c4d10",
                }
            }
        },
    }


_ERRORS: dict[int, dict[str, Any]] = {
    400: _error("The request cannot be completed", "BAD_REQUEST", "The request could not be processed."),
    401: _error(
        "Missing, invalid or revoked access token", "INVALID_TOKEN", "Your access token is invalid or has expired."
    ),
    403: _error("Not permitted", "PERMISSION_DENIED", "You do not have permission to perform this action."),
    404: _error("Record not found", "COURSE_NOT_FOUND", "Course not found."),
    409: _error("Duplicate or conflicting data", "DUPLICATE_DATA", "A record with the same details already exists."),
    422: _error(
        "Validation failed",
        "INVALID_DATA",
        "Some fields are missing or invalid.",
        [{"field": "slug", "code": "INVALID_SLUG", "message": "Must be lower-case letters, digits and hyphens"}],
    ),
    429: _error("Rate limit exceeded", "TOO_MANY_REQUESTS", "Too many requests. Please try again later."),
}

AUTHENTICATED = (401, 403, 422, 429)


def errors(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    return {code: _ERRORS[code] for code in sorted(set(status_codes))}
