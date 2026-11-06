"""Service configuration.

Every setting is read from environment variables (or a local ``.env`` file).
Development defaults exist only so the service boots locally; ``validate_security``
refuses to start staging/production with any of them.
"""

from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _private_or_https(url: str) -> bool:
    """https anywhere; plain http only to a private-network host: localhost, a loopback address, or a single-label
    container/service name such as ``user-management`` (resolvable only inside the deployment's own network)."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return parsed.scheme == "https" or (parsed.scheme == "http" and (host in {"localhost", "127.0.0.1", "::1"} or "." not in host))

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application ---
    APP_NAME: str = "lms-catalog-service"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["local", "test", "staging", "production"] = "local"
    DEBUG: bool = False
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_JSON: bool = True
    API_V1_PREFIX: str = "/api/v1"
    DOCS_ENABLED: bool = True
    CORS_ORIGINS: list[str] = Field(default_factory=list)
    TRUSTED_HOSTS: list[str] = Field(default_factory=lambda: ["*"])
    # Only enable behind a proxy you control; otherwise clients can spoof their IP.
    TRUST_PROXY_HEADERS: bool = False

    # --- Database (own database; never read another service's tables) ---
    DATABASE_URL: str = "postgresql+asyncpg://lms:lms@localhost:5432/lms_catalog"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT_SECONDS: int = 30
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_ECHO: bool = False
    # Any single query running longer than this is cancelled, so one slow query cannot exhaust the pool.
    DB_STATEMENT_TIMEOUT_MS: int = Field(default=15_000, ge=100)

    # --- Redis (rate limiting, access-state reads, event stream) ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Authentication: this service only verifies tokens, it never issues them ---
    # user-management's JWKS endpoint. Keys are cached in memory; see app/core/security.py.
    USER_MANAGEMENT_JWKS_URL: str = "http://localhost:8001/.well-known/jwks.json"
    JWT_ISSUER: str = "lms-user-management"
    JWT_AUDIENCE: str = "lms"
    JWT_LEEWAY_SECONDS: int = Field(default=10, ge=0, le=60)
    JWKS_CACHE_SECONDS: int = Field(default=300, ge=10)
    JWKS_FETCH_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0)

    # --- Access state published by user-management (read-only; see lms_common.access_state) ---
    ACCESS_STATE_KEY_PREFIX: str = "lms:access"

    # --- Course rules ---
    # A version goes to review only when every topic ends with its published topic test (course -> modules -> topics
    # -> lessons -> topic test). Turn off only for content that deliberately has no tests.
    REQUIRE_TOPIC_TESTS: bool = True
    # ...and when the course has its final test (the one that earns the certificate) chosen on its rules.
    REQUIRE_FINAL_TEST: bool = True

    # --- Rate limiting (per client IP unless stated) ---
    RATE_LIMIT_ENABLED: bool = True
    AUTHORING_RATE_LIMIT_PER_MINUTE: int = 60
    REVIEW_RATE_LIMIT_PER_MINUTE: int = 60

    # --- Events (transactional outbox relayed by the worker; consumed from lms:events) ---
    EVENTS_STREAM: str = "lms:events"
    EVENTS_STREAM_MAX_LENGTH: int = Field(default=1_000_000, ge=1_000)
    OUTBOX_BATCH_SIZE: int = Field(default=500, ge=1, le=5_000)
    EVENTS_CONSUMER_GROUP: str = "catalog-service"
    EVENTS_CONSUMER_NAME: str = "worker-1"
    EVENTS_BLOCK_MS: int = Field(default=5_000, ge=100)

    # --- Background worker (python -m app.worker: outbox relay + inbound event consumer) ---
    WORKER_POLL_SECONDS: float = Field(default=2.0, gt=0)

    # --- Course rule defaults (configurable per course version; see app/models/course_rule.py) ---
    DEFAULT_TOPIC_PASS_MARK: int = Field(default=60, ge=0, le=100)
    DEFAULT_MODULE_PASS_MARK: int = Field(default=60, ge=0, le=100)
    DEFAULT_FINAL_PASS_MARK: int = Field(default=60, ge=0, le=100)
    DEFAULT_FINAL_TEST_ATTEMPTS: int = Field(default=3, ge=1, le=10)
    DEFAULT_FINAL_TEST_COOLDOWN_DAYS: int = Field(default=7, ge=0, le=90)

    @property
    def is_production_like(self) -> bool:
        return self.ENVIRONMENT in {"staging", "production"}

    def validate_security(self) -> None:
        errors: list[str] = []
        if self.is_production_like:
            if self.DEBUG:
                errors.append("DEBUG must be false outside local/test")
            if "*" in self.TRUSTED_HOSTS:
                errors.append("TRUSTED_HOSTS must list explicit hosts outside local/test")
            if not _private_or_https(self.USER_MANAGEMENT_JWKS_URL):
                errors.append("USER_MANAGEMENT_JWKS_URL must use https outside local/test")
        if errors:
            raise ValueError("; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_security()
    return settings
