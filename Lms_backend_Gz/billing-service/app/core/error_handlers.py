import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

_HTTP_ERRORS = {
    400: ("BAD_REQUEST", "The request could not be processed."),
    401: ("AUTHENTICATION_FAILED", "Authentication failed."),
    403: ("PERMISSION_DENIED", "You do not have permission to perform this action."),
    404: ("URL_NOT_FOUND", "The requested URL does not exist."),
    405: ("METHOD_NOT_ALLOWED", "This HTTP method is not supported for this URL."),
    413: ("PAYLOAD_TOO_LARGE", "The request body is too large."),
    415: ("UNSUPPORTED_MEDIA_TYPE", "Send the request body as application/json."),
}

# Friendlier wording for Pydantic's built-in error types.
_VALIDATION_MESSAGES = {
    "missing": ("REQUIRED", "This field is required"),
    "extra_forbidden": ("UNKNOWN_FIELD", "This field is not allowed"),
    "json_invalid": ("INVALID_JSON", "The request body is not valid JSON"),
    "model_attributes_type": ("INVALID_TYPE", "Must be an object"),
    "dict_type": ("INVALID_TYPE", "Must be an object"),
    "list_type": ("INVALID_TYPE", "Must be a list"),
    "string_type": ("INVALID_TYPE", "Must be a string"),
    "int_type": ("INVALID_TYPE", "Must be a whole number"),
    "int_parsing": ("INVALID_TYPE", "Must be a whole number"),
    "bool_type": ("INVALID_TYPE", "Must be true or false"),
    "bool_parsing": ("INVALID_TYPE", "Must be true or false"),
    "date_type": ("INVALID_DATE", "Must be a date in YYYY-MM-DD format"),
    "date_from_datetime_parsing": ("INVALID_DATE", "Must be a date in YYYY-MM-DD format"),
    "date_parsing": ("INVALID_DATE", "Must be a date in YYYY-MM-DD format"),
    "too_long": ("TOO_MANY_ITEMS", "Too many items"),
    "string_too_short": ("TOO_SHORT", None),
    "string_too_long": ("TOO_LONG", None),
    "string_pattern_mismatch": ("INVALID_FORMAT", "Has an invalid format"),
    "enum": ("INVALID_OPTION", None),
    "literal_error": ("INVALID_OPTION", None),
    "greater_than_equal": ("OUT_OF_RANGE", None),
    "less_than_equal": ("OUT_OF_RANGE", None),
}


def error_body(request: Request, code: str, message: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "status": "error",
        "code": code,
        "message": message,
        "details": details or [],
        "request_id": getattr(request.state, "request_id", None),
    }


def _field_path(location: tuple[Any, ...]) -> str | None:
    parts = [str(part) for part in location[1:] if not (isinstance(part, str) and ("[" in part or "-" in part))]
    if location and location[0] in {"query", "path", "header"}:
        return ".".join(parts) or None
    return ".".join(parts) or None


def _validation_detail(error: dict[str, Any]) -> dict[str, Any]:
    error_type = str(error["type"])
    message = str(error["msg"]).removeprefix("Value error, ")
    code, friendly = _VALIDATION_MESSAGES.get(error_type, (error_type if error_type.isupper() else "INVALID_VALUE", None))
    return {"field": _field_path(tuple(error["loc"])), "code": code, "message": friendly or message}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=error_body(request, exc.code, exc.message, exc.details), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Submitted values are never echoed back: they may contain passwords or PII.
        details = [_validation_detail(error) for error in exc.errors()]
        return JSONResponse(status_code=422, content=error_body(request, "INVALID_DATA", "Some fields are missing or invalid.", details))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _HTTP_ERRORS.get(exc.status_code, ("HTTP_ERROR", str(exc.detail)))
        return JSONResponse(status_code=exc.status_code, content=error_body(request, code, message), headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error while processing request")
        return JSONResponse(status_code=500, content=error_body(request, "INTERNAL_ERROR", "Something went wrong on our side. Please try again."))
