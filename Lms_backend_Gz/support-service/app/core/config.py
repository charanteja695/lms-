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

# Minutes, by priority. Wall-clock time (no business-hours calendar yet); a queue/priority pair can be overridden
# in the database (``sla_policies``), these are the platform defaults.
DEFAULT_FIRST_RESPONSE_MINUTES = {"urgent": 30, "high": 120, "normal": 480, "low": 1_440}
DEFAULT_RESOLUTION_MINUTES = {"urgent": 240, "high": 1_440, "normal": 4_320, "low": 10_080}



def _private_or_https(url: str) -> bool:
    """https anywhere; plain http only to a private-network host: localhost, a loopback address, or a single-label
    container/service name such as ``user-management`` (resolvable only inside the deployment's own network)."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return parsed.scheme == "https" or (parsed.scheme == "http" and (host in {"localhost", "127.0.0.1", "::1"} or "." not in host))

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application ---
    APP_NAME: str = "lms-support-service"
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
    DATABASE_URL: str = "postgresql+asyncpg://lms:lms@localhost:5432/lms_support"
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

    # --- ai-tutor-service: the conversation behind a tutor hand-off, read with the internal token ---
    AI_TUTOR_SERVICE_URL: str = "http://localhost:8011"
    # Asked who holds a permission before a ticket is assigned to them (POST /internal/permission-holders).
    USER_MANAGEMENT_URL: str = "http://localhost:8001"
    USER_MANAGEMENT_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0)
    AI_TUTOR_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0)

    # --- Rate limits ---
    RATE_LIMIT_ENABLED: bool = True
    TICKET_RATE_LIMIT_PER_USER_PER_HOUR: int = Field(default=10, ge=1)
    REPLY_RATE_LIMIT_PER_USER_PER_MINUTE: int = Field(default=20, ge=1)
    AGENT_RATE_LIMIT_PER_HOUR: int = Field(default=2_000, ge=1)

    # --- Events (transactional outbox relayed by the worker; consumed from lms:events) ---
    EVENTS_STREAM: str = "lms:events"
    EVENTS_STREAM_MAX_LENGTH: int = Field(default=1_000_000, ge=1_000)
    OUTBOX_BATCH_SIZE: int = Field(default=500, ge=1, le=5_000)
    EVENTS_CONSUMER_GROUP: str = "support-service"
    EVENTS_CONSUMER_NAME: str = "worker-1"
    EVENTS_BLOCK_MS: int = Field(default=5_000, ge=100)
    PROCESSED_EVENTS_RETENTION_DAYS: int = Field(default=14, ge=1)
    WORKER_POLL_SECONDS: float = Field(default=2.0, gt=0)
    HOUSEKEEPING_INTERVAL_SECONDS: float = Field(default=3600.0, gt=0)

    # --- Ticket lifecycle ---
    MAX_SUBJECT_CHARS: int = Field(default=200, ge=20)
    MAX_BODY_CHARS: int = Field(default=6_000, ge=100)
    # A resolved ticket the student does not answer is closed after this long; within the reopen window a student's
    # reply reopens it, after it they open a new ticket.
    AUTO_CLOSE_AFTER_DAYS: int = Field(default=7, ge=1)
    REOPEN_WINDOW_DAYS: int = Field(default=7, ge=1)
    SLA_SWEEP_BATCH: int = Field(default=500, ge=1)
    SLA_SWEEP_SECONDS: float = Field(default=30.0, gt=0)

    # --- Attachments (screenshots, logs, documents on a message; uploaded straight to S3 with a presigned POST) ---
    AWS_REGION: str = "ap-south-1"
    AWS_ACCESS_KEY_ID: SecretStr | None = None
    AWS_SECRET_ACCESS_KEY: SecretStr | None = None
    S3_BUCKET: str = "lms-support-dev"
    # Set only for local testing against a non-AWS S3-compatible endpoint; unset in staging/production.
    S3_ENDPOINT_URL: str | None = None
    S3_UPLOAD_URL_EXPIRES_SECONDS: int = Field(default=900, ge=60, le=3_600)
    S3_DOWNLOAD_URL_EXPIRES_SECONDS: int = Field(default=300, ge=30, le=3_600)
    ATTACHMENT_MAX_MB: int = Field(default=10, ge=1, le=100)
    ATTACHMENT_MAX_FILES: int = Field(default=5, ge=1, le=20)
    ATTACHMENT_ALLOWED_EXTENSIONS: list[str] = Field(
        default_factory=lambda: ["png", "jpg", "jpeg", "gif", "webp", "pdf", "txt", "log", "csv", "doc", "docx", "xls", "xlsx", "zip"]
    )
    ATTACHMENT_URL_RATE_LIMIT_PER_USER_PER_MINUTE: int = Field(default=30, ge=1)

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
            if self.S3_ENDPOINT_URL is not None and not self.S3_ENDPOINT_URL.startswith("https://"):
                errors.append("S3_ENDPOINT_URL must be unset (AWS S3) or an https URL (S3-compatible storage) outside local/test")
            if self.S3_BUCKET == "lms-support-dev":
                errors.append("S3_BUCKET still uses the development default")
        if errors:
            raise ValueError("; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_security()
    return settings
