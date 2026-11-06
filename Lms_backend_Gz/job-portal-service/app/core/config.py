"""Service configuration.

Every setting is read from environment variables (or a local ``.env`` file).
Development defaults exist only so the service boots locally; ``validate_security``
refuses to start staging/production with any of them.
"""

from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_MARKER = "insecure-dev"



def _private_or_https(url: str) -> bool:
    """https anywhere; plain http only to a private-network host: localhost, a loopback address, or a single-label
    container/service name such as ``user-management`` (resolvable only inside the deployment's own network)."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return parsed.scheme == "https" or (parsed.scheme == "http" and (host in {"localhost", "127.0.0.1", "::1"} or "." not in host))

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application ---
    APP_NAME: str = "lms-job-portal-service"
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
    DATABASE_URL: str = "postgresql+asyncpg://lms:lms@localhost:5432/lms_job_portal"
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
    INTERNAL_SERVICE_TOKEN: SecretStr = SecretStr(f"{DEV_SECRET_MARKER}-internal-service-token-change-me-0")

    # --- Other services (synchronous calls use the internal token) ---
    AI_GATEWAY_URL: str = "http://localhost:8010"
    AI_GATEWAY_TIMEOUT_SECONDS: float = Field(default=45.0, gt=0)
    ASSESSMENT_SERVICE_URL: str = "http://localhost:8007"
    ASSESSMENT_SERVICE_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0)
    CAREER_SERVICE_URL: str = "http://localhost:8013"
    CAREER_SERVICE_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0)
    PLATFORM_ORGANIZATION_ID: int = Field(default=1755000000000001, ge=1)  # billed for AI calls made on the platform's behalf
    MAX_TOKENS: int = Field(default=700, ge=50, le=4_096)

    # --- Rate limits ---
    RATE_LIMIT_ENABLED: bool = True
    WRITE_RATE_LIMIT_PER_USER_PER_MINUTE: int = Field(default=60, ge=1)
    APPLY_RATE_LIMIT_PER_USER_PER_HOUR: int = Field(default=30, ge=1)
    AI_RATE_LIMIT_PER_USER_PER_HOUR: int = Field(default=60, ge=1)

    # --- Events (transactional outbox relayed by the worker; consumed from lms:events) ---
    EVENTS_STREAM: str = "lms:events"
    EVENTS_STREAM_MAX_LENGTH: int = Field(default=1_000_000, ge=1_000)
    OUTBOX_BATCH_SIZE: int = Field(default=500, ge=1, le=5_000)
    EVENTS_CONSUMER_GROUP: str = "job-portal-service"
    EVENTS_CONSUMER_NAME: str = "worker-1"
    EVENTS_BLOCK_MS: int = Field(default=5_000, ge=100)
    PROCESSED_EVENTS_RETENTION_DAYS: int = Field(default=14, ge=1)
    WORKER_POLL_SECONDS: float = Field(default=2.0, gt=0)
    HOUSEKEEPING_INTERVAL_SECONDS: float = Field(default=3600.0, gt=0)

    # --- Jobs ---
    MAX_OPEN_JOBS_PER_EMPLOYER: int = Field(default=200, ge=1)
    MAX_SKILLS_PER_JOB: int = Field(default=30, ge=1)

    # --- Matching (docs/PRODUCT.md §5.7) ---
    # A match score is the sum of these weights' shares; they must add up to 100.
    MATCH_WEIGHT_SKILLS: int = Field(default=50, ge=0, le=100)
    MATCH_WEIGHT_SEMANTIC: int = Field(default=20, ge=0, le=100)
    MATCH_WEIGHT_CERTIFICATES: int = Field(default=10, ge=0, le=100)
    MATCH_WEIGHT_PREFERENCES: int = Field(default=20, ge=0, le=100)
    MATCH_STORE_MIN_SCORE: int = Field(default=30, ge=0, le=100)  # matches below this are not kept (they would never be shown)
    MATCH_NOTIFY_MIN_SCORE: int = Field(default=70, ge=0, le=100)  # a student is told about a job at or above this
    MATCH_BATCH_SIZE: int = Field(default=200, ge=1)  # candidates scored per work item of a job
    RECOMMENDATIONS_DEFAULT_LIMIT: int = Field(default=20, ge=1, le=100)

    # --- Applications and screening ---
    SCREEN_AI_ENABLED: bool = True
    SCREEN_SHORTLIST_DEFAULT_THRESHOLD: int = Field(default=70, ge=0, le=100)  # a screening score at or above this is recommended for shortlisting
    SCREEN_REJECT_BELOW: int = Field(default=40, ge=0, le=100)  # below this, rejection is recommended (a person still has to confirm it)
    OFFER_DEFAULT_VALID_DAYS: int = Field(default=7, ge=1)
    ASSESSMENT_INVITE_VALID_DAYS: int = Field(default=7, ge=1)

    # --- Work queue (leased with SKIP LOCKED; retried with backoff) ---
    WORK_LEASE_SECONDS: int = Field(default=120, ge=10)
    WORK_MAX_ATTEMPTS: int = Field(default=6, ge=1)
    WORK_BACKOFF_BASE_SECONDS: int = Field(default=30, ge=1)
    WORK_BATCH: int = Field(default=10, ge=1)
    WORK_RETENTION_DAYS: int = Field(default=14, ge=1)

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
            if DEV_SECRET_MARKER in self.INTERNAL_SERVICE_TOKEN.get_secret_value():
                errors.append("INTERNAL_SERVICE_TOKEN still uses the development default")
        weights = self.MATCH_WEIGHT_SKILLS + self.MATCH_WEIGHT_SEMANTIC + self.MATCH_WEIGHT_CERTIFICATES + self.MATCH_WEIGHT_PREFERENCES
        if weights != 100:
            errors.append(f"the MATCH_WEIGHT_* settings must add up to 100 (they add up to {weights})")
        if errors:
            raise ValueError("; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_security()
    return settings
