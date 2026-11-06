"""Service configuration.

Every setting is read from environment variables (or a local ``.env`` file).
Development defaults exist only so the service boots locally; ``validate_security``
refuses to start staging/production with any of them.
"""

import base64
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_MARKER = "insecure-dev"
# A valid Fernet key (32 url-safe base64 bytes) that is recognisably a development value.
DEV_ENCRYPTION_KEY = base64.urlsafe_b64encode(b"insecure-dev-test-case-key-0000!").decode()



def _private_or_https(url: str) -> bool:
    """https anywhere; plain http only to a private-network host: localhost, a loopback address, or a single-label
    container/service name such as ``user-management`` (resolvable only inside the deployment's own network)."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return parsed.scheme == "https" or (parsed.scheme == "http" and (host in {"localhost", "127.0.0.1", "::1"} or "." not in host))

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application ---
    APP_NAME: str = "lms-code-execution-service"
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
    DATABASE_URL: str = "postgresql+asyncpg://lms:lms@localhost:5432/lms_code_execution"
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

    # --- Callers that are services, not people (assessment-service submits on a student's behalf) ---
    # Same shared-secret scheme as subscription-service's seat endpoints: there is no per-service identity yet.
    INTERNAL_SERVICE_TOKEN: SecretStr = SecretStr(f"{DEV_SECRET_MARKER}-internal-service-token-change-me-0")

    # --- Rate limits: per user and per institution, per minute (docs/PRODUCT.md §5.2) ---
    RATE_LIMIT_ENABLED: bool = True
    RUN_RATE_LIMIT_PER_USER_PER_MINUTE: int = Field(default=20, ge=1)
    RUN_RATE_LIMIT_PER_ORG_PER_MINUTE: int = Field(default=600, ge=1)
    SUBMISSION_RATE_LIMIT_PER_USER_PER_MINUTE: int = Field(default=10, ge=1)
    SUBMISSION_RATE_LIMIT_PER_ORG_PER_MINUTE: int = Field(default=300, ge=1)
    AUTHORING_RATE_LIMIT_PER_HOUR: int = Field(default=600, ge=1)

    # --- Events (transactional outbox relayed by the worker) ---
    EVENTS_STREAM: str = "lms:events"
    EVENTS_STREAM_MAX_LENGTH: int = Field(default=1_000_000, ge=1_000)
    OUTBOX_BATCH_SIZE: int = Field(default=500, ge=1, le=5_000)

    # --- Execution engine ---
    # judge0: a self-hosted Judge0-compatible engine (docs/PRODUCT.md D4), the only choice outside
    # local/test. local: runs code as a plain subprocess of this machine with NO isolation, for
    # development and tests only (only languages that declare a local command).
    EXECUTION_ENGINE: Literal["judge0", "local"] = "local"
    JUDGE0_URL: str = "http://localhost:2358"
    JUDGE0_AUTH_TOKEN: SecretStr | None = None
    JUDGE0_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0)
    LANGUAGES_FILE: str = "runtimes/languages.json"

    # --- Limits on what a caller may send and what a run may use ---
    MAX_SOURCE_BYTES: int = Field(default=65_536, ge=1_024)
    MAX_STDIN_BYTES: int = Field(default=65_536, ge=0)
    MAX_OUTPUT_BYTES: int = Field(default=65_536, ge=1_024)
    RUN_CPU_TIME_SECONDS: float = Field(default=5.0, gt=0)
    RUN_WALL_TIME_SECONDS: float = Field(default=10.0, gt=0)
    RUN_MEMORY_MB: int = Field(default=256, ge=16)
    PROBLEM_MAX_TIME_LIMIT_MS: int = Field(default=15_000, ge=100)
    PROBLEM_MAX_MEMORY_MB: int = Field(default=512, ge=16)
    MAX_TEST_CASES_PER_PROBLEM: int = Field(default=200, ge=1)
    MAX_TEST_CASE_BYTES: int = Field(default=1_000_000, ge=1_024)

    # --- SQL problems: the student's query runs in a throw-away database ---
    SQL_MAX_ROWS: int = Field(default=1_000, ge=1)
    # PostgreSQL dialect: a low-privilege role on a DEDICATED sandbox cluster (never the service database).
    SQL_POSTGRES_DSN: str | None = None

    # --- Job queue (runs and submissions are rows claimed by workers with a lease) ---
    JOB_BATCH_SIZE: int = Field(default=10, ge=1, le=200)
    JOB_MAX_ATTEMPTS: int = Field(default=3, ge=1, le=10)
    JOB_LEASE_SECONDS: int = Field(default=120, ge=10)
    WORKER_CONCURRENCY: int = Field(default=8, ge=1, le=256)
    JUDGE_CASE_CONCURRENCY: int = Field(default=4, ge=1, le=64)
    WORKER_POLL_SECONDS: float = Field(default=0.5, gt=0)
    RESULT_WAIT_MAX_SECONDS: float = Field(default=30.0, gt=0)
    RESULT_POLL_INTERVAL_SECONDS: float = Field(default=0.25, gt=0)

    # --- Test case encryption at rest: comma-separated Fernet keys, newest first; older keys only decrypt ---
    TEST_CASE_ENCRYPTION_KEYS: SecretStr = SecretStr(DEV_ENCRYPTION_KEY)

    # --- Plagiarism (token fingerprints, docs/PRODUCT.md §5.2) ---
    SIMILARITY_FLAG_PERCENT: int = Field(default=80, ge=1, le=100)
    SIMILARITY_LIST_MIN_PERCENT: int = Field(default=30, ge=1, le=100)  # reviewers are not shown weaker matches
    SIMILARITY_MIN_TOKENS: int = Field(default=30, ge=5)
    FINGERPRINT_MAX_HASHES: int = Field(default=500, ge=50)

    # --- Housekeeping ---
    RUNS_RETENTION_DAYS: int = Field(default=30, ge=1)
    IDEMPOTENCY_RETENTION_HOURS: int = Field(default=24, ge=1)
    HOUSEKEEPING_INTERVAL_SECONDS: float = Field(default=3600.0, gt=0)

    @property
    def worker_db_pool_size(self) -> int:
        """Connections a worker keeps open: each execution in flight touches the database briefly at the start and
        the end, so about one connection per slot plus the claimer, the outbox relay and housekeeping. Below this,
        the pool opens and discards connections all day (measured: ~9x lower throughput)."""
        return max(self.DB_POOL_SIZE, self.WORKER_CONCURRENCY + 6)

    @property
    def is_production_like(self) -> bool:
        return self.ENVIRONMENT in {"staging", "production"}

    @property
    def encryption_keys(self) -> list[str]:
        return [key.strip() for key in self.TEST_CASE_ENCRYPTION_KEYS.get_secret_value().split(",") if key.strip()]

    def validate_security(self) -> None:
        errors: list[str] = []
        from cryptography.fernet import Fernet

        if not self.encryption_keys:
            errors.append("TEST_CASE_ENCRYPTION_KEYS must hold at least one Fernet key")
        for key in self.encryption_keys:
            try:
                Fernet(key)
            except ValueError:
                errors.append("TEST_CASE_ENCRYPTION_KEYS holds a value that is not a valid Fernet key")
                break
        if self.is_production_like:
            if self.DEBUG:
                errors.append("DEBUG must be false outside local/test")
            if "*" in self.TRUSTED_HOSTS:
                errors.append("TRUSTED_HOSTS must list explicit hosts outside local/test")
            if not _private_or_https(self.USER_MANAGEMENT_JWKS_URL):
                errors.append("USER_MANAGEMENT_JWKS_URL must use https outside local/test")
            if DEV_SECRET_MARKER in self.INTERNAL_SERVICE_TOKEN.get_secret_value():
                errors.append("INTERNAL_SERVICE_TOKEN still uses the development default")
            if DEV_ENCRYPTION_KEY in self.encryption_keys:
                errors.append("TEST_CASE_ENCRYPTION_KEYS still uses the development key")
            if self.EXECUTION_ENGINE == "local":
                errors.append("EXECUTION_ENGINE=local runs code without isolation and is not allowed outside local/test")
        if errors:
            raise ValueError("; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_security()
    return settings
