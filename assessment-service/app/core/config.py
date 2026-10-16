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
    APP_NAME: str = "lms-assessment-service"
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
    DATABASE_URL: str = "postgresql+asyncpg://lms:lms@localhost:5432/lms_assessment"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT_SECONDS: int = 30
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_ECHO: bool = False
    DB_STATEMENT_TIMEOUT_MS: int = Field(default=15_000, ge=100)

    # --- Redis (answer buffer, paper cache, waiting room, rate limiting, access-state reads, event stream) ---
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

    # --- Service-to-service: the same shared secret code-execution-service checks on /internal/* ---
    # (proctoring-service and job-portal-service call this service's /internal/* with it too; there is no
    # per-service identity scheme yet — same caveat as subscription-service's seat endpoints.)
    INTERNAL_SERVICE_TOKEN: SecretStr = SecretStr(f"{DEV_SECRET_MARKER}-internal-service-token-change-me-0")
    CODE_EXECUTION_URL: str = "http://localhost:8006"
    CODE_EXECUTION_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0)

    # --- Events (transactional outbox relayed by the worker; consumed from lms:events) ---
    EVENTS_STREAM: str = "lms:events"
    EVENTS_STREAM_MAX_LENGTH: int = Field(default=1_000_000, ge=1_000)
    OUTBOX_BATCH_SIZE: int = Field(default=500, ge=1, le=5_000)
    EVENTS_CONSUMER_GROUP: str = "assessment-service"
    EVENTS_CONSUMER_NAME: str = "worker-1"
    EVENTS_BLOCK_MS: int = Field(default=5_000, ge=100)
    PROCESSED_EVENTS_RETENTION_DAYS: int = Field(default=14, ge=1)

    # --- Rate limits (per user, per minute) ---
    RATE_LIMIT_ENABLED: bool = True
    ANSWER_SAVE_RATE_LIMIT_PER_USER_PER_MINUTE: int = Field(default=600, ge=1)
    ATTEMPT_CREATE_RATE_LIMIT_PER_USER_PER_MINUTE: int = Field(default=20, ge=1)
    FILE_URL_RATE_LIMIT_PER_USER_PER_MINUTE: int = Field(default=30, ge=1)
    AUTHORING_RATE_LIMIT_PER_HOUR: int = Field(default=1_200, ge=1)

    # --- Authoring limits ---
    MAX_SECTIONS_PER_TEST: int = Field(default=20, ge=1)
    MAX_QUESTIONS_PER_TEST: int = Field(default=300, ge=1)
    MAX_OPTIONS_PER_QUESTION: int = Field(default=12, ge=2)
    MAX_TEXT_BYTES: int = Field(default=20_000, ge=1_000)
    BULK_IMPORT_MAX_QUESTIONS: int = Field(default=200, ge=1)

    # --- Proctoring pre-check (proctoring-service publishes a Redis "ready" key when a student passes it) ---
    # A proctored test (basic or strict) cannot be started until the student's pre-check has passed. If Redis cannot
    # be read the start is allowed (and logged): an outage must not lock every student out of their exam.
    PROCTORING_PRECHECK_REQUIRED: bool = True
    PROCTORING_READY_KEY_PREFIX: str = "lms:proctor:ready"

    # --- Attempts: the server-side timer is the authority (docs/PRODUCT.md §5.1) ---
    # A save or submit that arrives this long after the deadline is still accepted (network latency, a slow
    # client clock is irrelevant since only the server clock counts); later ones are refused.
    ATTEMPT_GRACE_SECONDS: int = Field(default=10, ge=0, le=120)
    # A prepared (not started) attempt is dropped after this long without being started.
    PREPARED_ATTEMPT_TTL_HOURS: int = Field(default=12, ge=1)
    # Waiting room: a scheduled exam accepts attempt preparation this long before it opens.
    WAITING_ROOM_LEAD_MINUTES: int = Field(default=30, ge=0)
    # Starts admitted per second per test when an exam opens; the rest are told to retry (staggered start).
    WAITING_ROOM_ADMIT_PER_SECOND: int = Field(default=500, ge=1)
    MAX_ANSWER_BYTES: int = Field(default=70_000, ge=1_024)
    MAX_ANSWERS_PER_BATCH: int = Field(default=50, ge=1)

    # --- Question paper generation ---
    POOL_CACHE_SECONDS: int = Field(default=300, ge=0)  # eligible question ids per pool slot (Redis)
    POOL_MAX_CANDIDATES: int = Field(default=5_000, ge=10)

    # --- Answer buffer: writes hit Redis first and are flushed to the database in batches ---
    # "direct" writes straight to the database (also the automatic fallback when Redis is unavailable).
    ANSWER_BUFFER: Literal["redis", "direct"] = "redis"
    ANSWER_FLUSH_INTERVAL_SECONDS: float = Field(default=2.0, gt=0)
    ANSWER_FLUSH_BATCH_ATTEMPTS: int = Field(default=200, ge=1)
    ANSWER_BUFFER_TTL_HOURS: int = Field(default=48, ge=1)

    # --- Grading queue (submitted attempts are rows claimed by workers with a lease) ---
    JOB_BATCH_SIZE: int = Field(default=50, ge=1, le=500)
    JOB_LEASE_SECONDS: int = Field(default=120, ge=10)
    JOB_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=20)
    WORKER_CONCURRENCY: int = Field(default=8, ge=1, le=256)
    WORKER_POLL_SECONDS: float = Field(default=1.0, gt=0)
    TIMEOUT_SWEEP_BATCH: int = Field(default=500, ge=1)

    # --- Coding and SQL questions are judged by code-execution-service ---
    CODE_DISPATCH_BATCH: int = Field(default=50, ge=1, le=500)
    CODE_DISPATCH_MAX_ATTEMPTS: int = Field(default=6, ge=1, le=20)
    # A dispatched submission whose verdict event has not arrived is asked for directly after this long.
    CODE_RECONCILE_AFTER_SECONDS: int = Field(default=60, ge=5)
    # After this long without a verdict the answer is graded 0 and flagged for a human (never left hanging).
    CODE_GIVE_UP_MINUTES: int = Field(default=30, ge=1)

    # --- Proctoring integrity (proctoring-service emits integrity.*; docs/PRODUCT.md §5.3) ---
    # A proctored attempt waits for a human-confirmed or automatic integrity decision. Overdue ones are listed for
    # exams.manage; nothing is ever decided automatically on their behalf.
    INTEGRITY_DECISION_OVERDUE_HOURS: int = Field(default=72, ge=1)

    # --- Item statistics (difficulty index, discrimination) ---
    STATS_MIN_SAMPLE: int = Field(default=30, ge=2)
    STATS_SAMPLE_LIMIT: int = Field(default=5_000, ge=50)
    STATS_INTERVAL_SECONDS: float = Field(default=60.0, gt=0)

    # --- Object storage for file/project answers (presigned direct-to-S3 uploads) ---
    AWS_REGION: str = "ap-south-1"
    AWS_ACCESS_KEY_ID: SecretStr | None = None
    AWS_SECRET_ACCESS_KEY: SecretStr | None = None
    S3_BUCKET: str = "lms-assessment-dev"
    # Set only for local testing against a non-AWS S3-compatible endpoint; unset in staging/production.
    S3_ENDPOINT_URL: str | None = None
    S3_UPLOAD_URL_EXPIRES_SECONDS: int = Field(default=900, ge=60, le=3_600)
    S3_DOWNLOAD_URL_EXPIRES_SECONDS: int = Field(default=300, ge=30, le=3_600)
    ANSWER_FILE_MAX_MB: int = Field(default=25, ge=1, le=500)
    MAX_FILES_PER_ANSWER: int = Field(default=10, ge=1)

    # --- Housekeeping ---
    IDEMPOTENCY_RETENTION_HOURS: int = Field(default=24, ge=1)
    HOUSEKEEPING_INTERVAL_SECONDS: float = Field(default=3600.0, gt=0)

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
            if self.S3_BUCKET == "lms-assessment-dev":
                errors.append("S3_BUCKET still uses the development default")
        if errors:
            raise ValueError("; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_security()
    return settings
