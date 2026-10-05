"""Service configuration.

Every setting is read from environment variables (or a local ``.env`` file).
Development defaults exist only so the service boots locally; ``validate_security``
refuses to start staging/production with any of them.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application ---
    APP_NAME: str = "lms-notification-service"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["local", "test", "staging", "production"] = "local"
    DEBUG: bool = False
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_JSON: bool = True
    API_V1_PREFIX: str = "/api/v1"
    DOCS_ENABLED: bool = True
    CORS_ORIGINS: list[str] = Field(default_factory=list)
    TRUSTED_HOSTS: list[str] = Field(default_factory=lambda: ["*"])
    TRUST_PROXY_HEADERS: bool = False

    # --- Database (own database; never read another service's tables) ---
    DATABASE_URL: str = "postgresql+asyncpg://lms:lms@localhost:5432/lms_notification"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT_SECONDS: int = 30
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_ECHO: bool = False
    DB_STATEMENT_TIMEOUT_MS: int = Field(default=15_000, ge=100)

    # --- Redis (rate limiting, access-state reads, event stream) ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Authentication: this service only verifies tokens, it never issues them ---
    USER_MANAGEMENT_JWKS_URL: str = "http://localhost:8001/.well-known/jwks.json"
    JWT_ISSUER: str = "lms-user-management"
    JWT_AUDIENCE: str = "lms"
    JWT_LEEWAY_SECONDS: int = Field(default=10, ge=0, le=60)
    JWKS_CACHE_SECONDS: int = Field(default=300, ge=10)
    JWKS_FETCH_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0)

    # --- Access state published by user-management (read-only) ---
    ACCESS_STATE_KEY_PREFIX: str = "lms:access"

    # --- Rate limiting (per client IP unless stated) ---
    RATE_LIMIT_ENABLED: bool = True
    NOTIFICATION_WRITE_RATE_LIMIT_PER_HOUR: int = 600

    # --- Events (transactional outbox relayed by the worker; consumed from lms:events) ---
    EVENTS_STREAM: str = "lms:events"
    EVENTS_STREAM_MAX_LENGTH: int = Field(default=1_000_000, ge=1_000)
    OUTBOX_BATCH_SIZE: int = Field(default=500, ge=1, le=5_000)
    EVENTS_CONSUMER_GROUP: str = "notification-service"
    EVENTS_CONSUMER_NAME: str = "worker-1"
    EVENTS_BLOCK_MS: int = Field(default=5_000, ge=100)

    # --- Background worker (python -m app.worker: outbox relay + inbound event consumer) ---
    WORKER_POLL_SECONDS: float = Field(default=2.0, gt=0)

    # --- Delivery (worker sweep: pending emails are claimed, sent, then retried with backoff) ---
    DELIVERY_BATCH_SIZE: int = Field(default=50, ge=1, le=500)
    DELIVERY_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=20)
    DELIVERY_RETRY_BASE_SECONDS: int = Field(default=60, ge=1)
    DELIVERY_RETRY_MAX_SECONDS: int = Field(default=6 * 3600, ge=1)
    # A claimed delivery that is neither sent nor failed within this window is retried (worker crash).
    DELIVERY_CLAIM_LEASE_SECONDS: int = Field(default=120, ge=10)

    # --- Housekeeping ---
    PROCESSED_EVENTS_RETENTION_DAYS: int = Field(default=7, ge=1)
    HOUSEKEEPING_INTERVAL_SECONDS: float = Field(default=3600.0, gt=0)

    # --- Email channel ---
    EMAIL_BACKEND: Literal["console", "smtp"] = "console"
    EMAIL_FROM: str = "LMS <no-reply@lms.local>"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: SecretStr | None = None
    SMTP_STARTTLS: bool = True
    SMTP_USE_TLS: bool = False
    SMTP_TIMEOUT_SECONDS: int = 10
    # Exposed to templates as ${app_url}.
    FRONTEND_BASE_URL: str = "http://localhost:3000"

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
            if self.USER_MANAGEMENT_JWKS_URL.startswith("http://") and "localhost" not in self.USER_MANAGEMENT_JWKS_URL:
                errors.append("USER_MANAGEMENT_JWKS_URL must use https outside local/test")
            if self.EMAIL_BACKEND == "console":
                errors.append("EMAIL_BACKEND=console is not allowed outside local/test")
        if errors:
            raise ValueError("; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_security()
    return settings
