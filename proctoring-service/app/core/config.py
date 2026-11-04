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
    APP_NAME: str = "lms-proctoring-service"
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
    DATABASE_URL: str = "postgresql+asyncpg://lms:lms@localhost:5432/lms_proctoring"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT_SECONDS: int = 30
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_ECHO: bool = False
    DB_STATEMENT_TIMEOUT_MS: int = Field(default=15_000, ge=100)

    # --- Redis (ready flags read by assessment-service, rate limiting, access-state reads, event stream) ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Authentication: this service only verifies tokens, it never issues them ---
    USER_MANAGEMENT_JWKS_URL: str = "http://127.0.0.1:8001/.well-known/jwks.json"
    JWT_ISSUER: str = "lms-user-management"
    JWT_AUDIENCE: str = "lms"
    JWT_LEEWAY_SECONDS: int = Field(default=10, ge=0, le=60)
    JWKS_CACHE_SECONDS: int = Field(default=300, ge=10)
    JWKS_FETCH_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0)
    ACCESS_STATE_KEY_PREFIX: str = "lms:access"

    # --- Service-to-service: the shared secret assessment-service checks on its /internal/* ---
    INTERNAL_SERVICE_TOKEN: SecretStr = SecretStr(f"{DEV_SECRET_MARKER}-internal-service-token-change-me-0")
    ASSESSMENT_SERVICE_URL: str = "http://127.0.0.1:8007"
    ASSESSMENT_SERVICE_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0)
    # assessment-service reads this Redis key to know a student passed the pre-check before it starts their clock.
    READY_KEY_PREFIX: str = "lms:proctor:ready"
    READY_TTL_SECONDS: int = Field(default=7_200, ge=60)

    # --- AI analysis of snapshots and audio (docs/PRODUCT.md §5.3). Unset: snapshots are stored but not analysed, and
    # every report says so. The analyzer is any HTTP service implementing app/clients/analyzer.py's contract. ---
    AI_ANALYZER_URL: str | None = None
    AI_ANALYZER_TOKEN: SecretStr | None = None
    AI_ANALYZER_TIMEOUT_SECONDS: float = Field(default=20.0, gt=0)
    AI_MIN_CONFIDENCE: float = Field(default=0.6, ge=0, le=1)

    # --- Rate limits ---
    RATE_LIMIT_ENABLED: bool = True
    EVENTS_RATE_LIMIT_PER_SESSION_PER_MINUTE: int = Field(default=120, ge=1)
    SNAPSHOT_RATE_LIMIT_PER_SESSION_PER_MINUTE: int = Field(default=12, ge=1)  # one every 20-30 s, with headroom

    # --- Sessions and pre-check ---
    CONSENT_VERSION: str = "2026-09"
    MIN_BANDWIDTH_KBPS_STRICT: int = Field(default=300, ge=0)
    SNAPSHOT_INTERVAL_SECONDS: int = Field(default=25, ge=5)  # what the client is told to use (20-30 s)
    # Strict: a short microphone clip every AUDIO_INTERVAL_SECONDS for the voice check (0 turns clips off).
    AUDIO_INTERVAL_SECONDS: int = Field(default=60, ge=0)
    AUDIO_CLIP_SECONDS: int = Field(default=8, ge=2, le=30)
    HEARTBEAT_INTERVAL_SECONDS: int = Field(default=15, ge=5)
    HEARTBEAT_LOST_AFTER_SECONDS: int = Field(default=60, ge=10)
    MAX_EVENTS_PER_REQUEST: int = Field(default=100, ge=1)
    CLIENT_CLOCK_SKEW_SECONDS: int = Field(default=300, ge=0)  # an event dated further out than this is stamped now
    S3_UPLOAD_URL_EXPIRES_SECONDS: int = Field(default=300, ge=30, le=3_600)
    S3_DOWNLOAD_URL_EXPIRES_SECONDS: int = Field(default=120, ge=30, le=3_600)
    MAX_SNAPSHOT_MB: int = Field(default=5, ge=1, le=50)
    # Strict: before the test the student turns their face left, right, up and down; one frame per pose is kept.
    LIVENESS_REQUIRED: bool = True
    # Strict: the whole test is recorded (camera + microphone) and uploaded in chunks of VIDEO_CHUNK_SECONDS.
    VIDEO_RECORDING_ENABLED: bool = True
    VIDEO_CHUNK_SECONDS: int = Field(default=30, ge=5, le=300)
    MAX_VIDEO_CHUNK_MB: int = Field(default=25, ge=1, le=200)

    # --- Risk and integrity decisions (app/risk/policy.py has the per-event weights) ---
    # At or below this a finished attempt is cleared automatically; above it (or on any critical finding) a person decides.
    RISK_CLEAR_MAX: int = Field(default=25, ge=0, le=100)
    RISK_FLAG_MIN: int = Field(default=50, ge=1, le=100)  # crossing it live raises integrity.flagged and lights the monitor
    # After submission, wait this long for pending snapshot analysis before deciding on what is known.
    ANALYSIS_WAIT_SECONDS: int = Field(default=300, ge=0)
    APPEAL_WINDOW_DAYS: int = Field(default=7, ge=1)
    MIN_INVALIDATION_NOTE_CHARS: int = Field(default=10, ge=1)
    # Cases nobody has decided after this long are listed as overdue (never decided automatically).
    CASE_OVERDUE_HOURS: int = Field(default=72, ge=1)

    # --- Analysis queue ---
    ANALYSIS_BATCH: int = Field(default=20, ge=1, le=200)
    ANALYSIS_LEASE_SECONDS: int = Field(default=120, ge=10)
    ANALYSIS_MAX_ATTEMPTS: int = Field(default=4, ge=1, le=10)
    # Under load (docs/PRODUCT.md §8: "sampling when under load"): above this many waiting snapshots only every
    # ANALYSIS_SAMPLE_EVERY-th periodic snapshot of a session is analysed; the rest are stored and marked sampled out.
    ANALYSIS_BACKLOG_SAMPLING_THRESHOLD: int = Field(default=5_000, ge=1)
    ANALYSIS_SAMPLE_EVERY: int = Field(default=3, ge=2)

    # --- Events (transactional outbox relayed by the worker; consumed from lms:events) ---
    EVENTS_STREAM: str = "lms:events"
    EVENTS_STREAM_MAX_LENGTH: int = Field(default=1_000_000, ge=1_000)
    OUTBOX_BATCH_SIZE: int = Field(default=500, ge=1, le=5_000)
    EVENTS_CONSUMER_GROUP: str = "proctoring-service"
    EVENTS_CONSUMER_NAME: str = "worker-1"
    EVENTS_BLOCK_MS: int = Field(default=5_000, ge=100)
    PROCESSED_EVENTS_RETENTION_DAYS: int = Field(default=14, ge=1)
    WORKER_POLL_SECONDS: float = Field(default=2.0, gt=0)

    # --- Privacy (DPDP Act): media is kept for a fixed period and then deleted from storage ---
    MEDIA_RETENTION_DAYS: int = Field(default=90, ge=1)
    EVENTS_RETENTION_DAYS: int = Field(default=365, ge=30)  # the timeline of a decided case; media goes much sooner

    # --- Object storage for snapshots (direct-to-S3 uploads) ---
    AWS_REGION: str = "ap-south-1"
    AWS_ACCESS_KEY_ID: SecretStr | None = None
    AWS_SECRET_ACCESS_KEY: SecretStr | None = None
    S3_BUCKET: str = "lms-proctoring-dev"
    # Set only for local testing against a non-AWS S3-compatible endpoint; unset in staging/production.
    S3_ENDPOINT_URL: str | None = None

    # --- Housekeeping ---
    HOUSEKEEPING_INTERVAL_SECONDS: float = Field(default=3600.0, gt=0)

    @property
    def is_production_like(self) -> bool:
        return self.ENVIRONMENT in {"staging", "production"}

    def validate_security(self) -> None:
        errors: list[str] = []
        if self.RISK_CLEAR_MAX >= self.RISK_FLAG_MIN:
            errors.append("RISK_CLEAR_MAX must be below RISK_FLAG_MIN")
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
            if self.S3_BUCKET == "lms-proctoring-dev":
                errors.append("S3_BUCKET still uses the development default")
        if errors:
            raise ValueError("; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_security()
    return settings
