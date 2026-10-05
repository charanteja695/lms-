"""Settings validation: what staging/production refuse to start with."""

import pytest

from app.core.config import Settings


def _settings(**overrides):
    values = {"ENVIRONMENT": "local", "JWT_ISSUER": "lms-user-management", "JWT_AUDIENCE": "lms"}
    values.update(overrides)
    return Settings(**values)


def test_local_defaults_start_fine():
    _settings().validate_security()


@pytest.mark.parametrize(
    "overrides",
    [{"DEBUG": True, "CORS_ORIGINS": ["https://app.example"]}, {"TRUSTED_HOSTS": ["*"], "CORS_ORIGINS": ["https://app.example"]}, {"CORS_ORIGINS": []},
     {"USER_MANAGEMENT_JWKS_URL": "http://jwks.example.com/.well-known/jwks.json", "CORS_ORIGINS": ["https://app.example"]}],
)
def test_production_refuses_development_defaults(overrides):
    with pytest.raises(ValueError):
        _settings(ENVIRONMENT="production", **overrides).validate_security()


def test_production_is_fine_once_configured():
    _settings(ENVIRONMENT="production", DEBUG=False, TRUSTED_HOSTS=["app.example"], CORS_ORIGINS=["https://app.example"], USER_MANAGEMENT_JWKS_URL="https://auth.example/.well-known/jwks.json").validate_security()


def test_upstream_urls_override_only_the_services_they_name():
    settings = _settings(UPSTREAM_URLS='{"user-management": "http://um:9001"}')
    merged = settings.upstreams()
    assert merged["user-management"] == "http://um:9001" and merged["billing-service"] == "http://localhost:8018"


def test_upstream_urls_must_be_a_json_object_of_strings():
    with pytest.raises(ValueError):
        _settings(UPSTREAM_URLS="not json").validate_security()
    with pytest.raises(ValueError):
        _settings(UPSTREAM_URLS='["a"]').validate_security()
    with pytest.raises(ValueError):
        _settings(UPSTREAM_URLS='{"a": 1}').validate_security()
