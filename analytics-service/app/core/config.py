"""Service configuration.

Every setting is read from environment variables (or a local ``.env`` file).
Development defaults exist only so the service boots locally; ``validate_security``
refuses to start staging/production with any of them.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application ---
    APP_NAME: str = "lms-analytics-service"
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

    # --- Database (own database; never read another service's tables). PostgreSQL, not ClickHouse: D12. ---
    DATABASE_URL: str = "postgresql+asyncpg://lms:lms@localhost:5432/lms_analytics"
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
    ACCESS_STATE_KEY_PREFIX: str = "lms:access"

    # --- Rate limiting ---
    RATE_LIMIT_ENABLED: bool = True
    WRITE_RATE_LIMIT_PER_HOUR: int = Field(default=200, ge=1)

    # --- Events (transactional outbox relayed by the worker; consumed from lms:events) ---
    EVENTS_STREAM: str = "lms:events"
    EVENTS_STREAM_MAX_LENGTH: int = Field(default=1_000_000, ge=1_000)
    OUTBOX_BATCH_SIZE: int = Field(default=500, ge=1, le=5_000)
    EVENTS_CONSUMER_GROUP: str = "analytics-service"
    EVENTS_CONSUMER_NAME: str = "worker-1"
    EVENTS_BLOCK_MS: int = Field(default=5_000, ge=100)
    PROCESSED_EVENTS_RETENTION_DAYS: int = Field(default=30, ge=1)  # longer than most: rollups may be recomputed from history
    WORKER_POLL_SECONDS: float = Field(default=2.0, gt=0)
    HOUSEKEEPING_INTERVAL_SECONDS: float = Field(default=3600.0, gt=0)

    # --- Rollups (docs/PRODUCT.md §5.9 "Aggregation") ---
    ROLLUP_INTERVAL_SECONDS: float = Field(default=300.0, gt=0)  # how often the worker recomputes the tail window
    ROLLUP_TAIL_DAYS: int = Field(default=2, ge=1, le=14)  # today + this many trailing days are recomputed each tick
    DASHBOARD_ROLLUP_CUTOFF_DAYS: int = Field(default=1, ge=0)  # a dashboard reads EventFact directly within this many days of "now"; rollups beyond it
    RAW_EVENT_RETENTION_DAYS: int = Field(default=400, ge=30)  # EventFact rows older than this are pruned; rollups (already computed) are kept forever

    # --- Scheduled reports ---
    REPORT_CHECK_INTERVAL_SECONDS: float = Field(default=300.0, gt=0)
    REPORT_MAX_ROWS: int = Field(default=5_000, ge=10)
    REPORT_RUN_RETENTION_COUNT: int = Field(default=20, ge=1)  # runs kept per definition; older ones are pruned

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
        if errors:
            raise ValueError("; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_security()
    return settings
