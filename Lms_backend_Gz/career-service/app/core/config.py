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
    APP_NAME: str = "lms-career-service"
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
    DATABASE_URL: str = "postgresql+asyncpg://lms:lms@localhost:5432/lms_career"
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

    # --- ai-gateway (every model call; this service holds no provider key) ---
    AI_GATEWAY_URL: str = "http://localhost:8010"
    AI_GATEWAY_TIMEOUT_SECONDS: float = Field(default=45.0, gt=0)
    PLATFORM_ORGANIZATION_ID: int = Field(default=1755000000000001, ge=1)  # billed for students who belong to no institution
    MAX_TOKENS: int = Field(default=900, ge=50, le=4_096)

    # --- Rate limits ---
    RATE_LIMIT_ENABLED: bool = True
    WRITE_RATE_LIMIT_PER_USER_PER_MINUTE: int = Field(default=60, ge=1)
    AI_RATE_LIMIT_PER_USER_PER_HOUR: int = Field(default=30, ge=1)
    EXPORT_RATE_LIMIT_PER_USER_PER_HOUR: int = Field(default=60, ge=1)
    PUBLIC_RATE_LIMIT_PER_IP_PER_MINUTE: int = Field(default=60, ge=1)

    # --- Events (transactional outbox relayed by the worker; consumed from lms:events) ---
    EVENTS_STREAM: str = "lms:events"
    EVENTS_STREAM_MAX_LENGTH: int = Field(default=1_000_000, ge=1_000)
    OUTBOX_BATCH_SIZE: int = Field(default=500, ge=1, le=5_000)
    EVENTS_CONSUMER_GROUP: str = "career-service"
    EVENTS_CONSUMER_NAME: str = "worker-1"
    EVENTS_BLOCK_MS: int = Field(default=5_000, ge=100)
    PROCESSED_EVENTS_RETENTION_DAYS: int = Field(default=14, ge=1)
    WORKER_POLL_SECONDS: float = Field(default=2.0, gt=0)
    HOUSEKEEPING_INTERVAL_SECONDS: float = Field(default=3600.0, gt=0)

    # --- Profile and resumes ---
    MAX_PROFILE_ITEMS_PER_KIND: int = Field(default=50, ge=5)
    MAX_RESUMES_PER_USER: int = Field(default=10, ge=1)
    MAX_VERSIONS_PER_RESUME: int = Field(default=50, ge=5)  # the oldest are pruned when a new one is saved
    MAX_BULLETS_PER_ITEM: int = Field(default=8, ge=1)
    MAX_BULLET_CHARS: int = Field(default=300, ge=50)
    MAX_JOB_DESCRIPTION_CHARS: int = Field(default=8_000, ge=500)
    SHARE_DEFAULT_DAYS: int = Field(default=30, ge=1, le=365)  # a share link with no explicit expiry lasts this long
    SHARE_EXPIRY_CHOICES: list[int] = Field(default_factory=lambda: [7, 30, 90])  # offered when a student shares (days, each 1-365)
    # Roles offered as one-tap suggestions when a resume is created (the student can type any role); the student's own target
    # roles are offered first. Set as a JSON list in the environment.
    RESUME_ROLE_SUGGESTIONS: list[str] = Field(
        default_factory=lambda: [
            "Frontend Developer", "Backend Developer", "Full Stack Developer", "Java Developer", "Python Developer", ".NET Developer", "Mobile App Developer",
            "Data Analyst", "Data Scientist", "DevOps Engineer", "Cloud Engineer", "QA / Test Engineer", "Cyber Security Analyst", "UI/UX Designer",
        ]
    )
    MAX_IMPORT_BYTES: int = Field(default=5 * 1024 * 1024, ge=100_000)  # an uploaded old resume / LinkedIn PDF
    MAX_IMPORT_TEXT_CHARS: int = Field(default=20_000, ge=2_000)  # text sent to the model from that file
    # A skill score shows a percentile only when at least this many students have a score for the course; a percentile
    # among five people would be noise, and would let a student be identified from the numbers.
    PERCENTILE_MIN_COHORT: int = Field(default=20, ge=2)

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
        if errors:
            raise ValueError("; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_security()
    return settings
