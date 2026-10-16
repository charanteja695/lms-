"""Production storage: AWS S3 (no endpoint) or an S3-compatible store over https, never plain http."""

import pytest

from app.core.config import Settings


def _storage_errors(endpoint: str | None) -> str:
    try:
        Settings(_env_file=None, ENVIRONMENT="production", S3_ENDPOINT_URL=endpoint).validate_security()
    except ValueError as exc:
        return str(exc)
    return ""


@pytest.mark.parametrize("endpoint", [None, "https://files.example.com"])
def test_aws_or_https_storage_is_accepted(endpoint):
    assert "S3_ENDPOINT_URL" not in _storage_errors(endpoint)


def test_plain_http_storage_is_refused():
    assert "S3_ENDPOINT_URL" in _storage_errors("http://minio:9000")
