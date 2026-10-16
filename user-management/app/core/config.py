"""Service configuration.

Every setting is read from environment variables (or a local ``.env`` file).
Development defaults exist only so the service boots locally; ``validate_security``
refuses to start staging/production with any of them.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_MARKER = "insecure-dev"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application ---
    APP_NAME: str = "lms-user-management"
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

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://lms:lms@localhost:5432/lms_user_management"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT_SECONDS: int = 30
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_ECHO: bool = False
    # Any single query running longer than this is cancelled, so one slow query cannot exhaust the pool.
    DB_STATEMENT_TIMEOUT_MS: int = Field(default=15_000, ge=100)

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- JWT ---
    # RS256 is recommended for microservices: other services verify tokens with the
    # public key (served at /.well-known/jwks.json) and never hold the signing key.
    JWT_ALGORITHM: Literal["HS256", "RS256"] = "HS256"
    JWT_SECRET_KEY: SecretStr = SecretStr(f"{DEV_SECRET_MARKER}-jwt-secret-change-me-000000000")
    JWT_PRIVATE_KEY_FILE: Path | None = None
    JWT_PUBLIC_KEY_FILE: Path | None = None
    JWT_KEY_ID: str = "lms-user-management-1"
    # Key rotation: keep the previous public key published (and accepted) until its tokens have expired.
    JWT_PREVIOUS_PUBLIC_KEY_FILE: Path | None = None
    JWT_PREVIOUS_KEY_ID: str | None = None
    JWT_ISSUER: str = "lms-user-management"
    JWT_AUDIENCE: str = "lms"
    JWT_LEEWAY_SECONDS: int = Field(default=10, ge=0, le=60)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, ge=1, le=60)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1, le=90)
    SESSION_MAX_LIFETIME_DAYS: int = Field(default=30, ge=1, le=365)

    # --- Browser sessions: refresh token in an httpOnly cookie (clients opt in with X-Session-Transport: cookie) ---
    REFRESH_COOKIE_NAME: str = "lms_refresh"
    REFRESH_COOKIE_PATH: str = "/api/v1/auth"
    REFRESH_COOKIE_DOMAIN: str | None = None
    REFRESH_COOKIE_SECURE: bool = True
    REFRESH_COOKIE_SAMESITE: Literal["strict", "lax"] = "strict"

    # --- Access state shared with other services (see app/core/access_state.py) ---
    ACCESS_STATE_KEY_PREFIX: str = "lms:access"
    # Other services call /internal with this shared secret (the same value in every service's settings).
    INTERNAL_SERVICE_TOKEN: SecretStr = SecretStr(f"{DEV_SECRET_MARKER}-internal-service-token-change-me-0")

    # --- Hashing ---
    # Server-side pepper used to HMAC refresh tokens, OTPs and reset links at rest.
    TOKEN_HASH_SECRET: SecretStr = SecretStr(f"{DEV_SECRET_MARKER}-token-hash-secret-change-me-0")
    ARGON2_TIME_COST: int = Field(default=3, ge=1)
    ARGON2_MEMORY_COST_KIB: int = Field(default=65536, ge=8)
    ARGON2_PARALLELISM: int = Field(default=4, ge=1)
    # Password hashes computed at once per instance. Each uses ARGON2_MEMORY_COST_KIB of RAM, so this bounds
    # memory during login bursts (e.g. 8 x 64 MB = 512 MB). Scale out instances for more throughput.
    PASSWORD_HASH_CONCURRENCY: int = Field(default_factory=lambda: max(2, os.cpu_count() or 2), ge=1, le=256)

    # --- Data defaults & rules ---
    # Used to interpret phone numbers entered without a +country code, and as profile defaults.
    DEFAULT_COUNTRY_CODE: str = Field(default="IN", pattern=r"^[A-Z]{2}$")
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"
    DEFAULT_LANGUAGE: str = "en"
    STUDENT_MIN_AGE: int = Field(default=3, ge=0, le=18)
    EMPLOYEE_MIN_AGE: int = Field(default=18, ge=14, le=25)
    GUARDIAN_REQUIRED_BELOW_AGE: int = Field(default=18, ge=0, le=25)

    # --- Password policy & lockout ---
    PASSWORD_MIN_LENGTH: int = Field(default=12, ge=8, le=64)
    MAX_FAILED_LOGIN_ATTEMPTS: int = Field(default=5, ge=1)
    ACCOUNT_LOCKOUT_MINUTES: int = Field(default=15, ge=1)

    # --- Password reset & account set-up ---
    OTP_LENGTH: int = Field(default=6, ge=6, le=10)
    OTP_EXPIRE_MINUTES: int = Field(default=10, ge=1, le=60)
    OTP_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=10)
    RESET_TOKEN_EXPIRE_MINUTES: int = Field(default=15, ge=1, le=60)
    ACCOUNT_SETUP_EXPIRE_HOURS: int = Field(default=72, ge=1, le=720)
    FRONTEND_BASE_URL: str = "http://localhost:3000"
    FRONTEND_LOGIN_PATH: str = "/login"
    FRONTEND_RESET_PASSWORD_PATH: str = "/reset-password"
    FRONTEND_ACCOUNT_SETUP_PATH: str = "/set-password"

    # --- Rate limiting (per client IP unless stated) ---
    RATE_LIMIT_ENABLED: bool = True
    # per client IP: a school shares one IP, so sized for a classroom; brute force is stopped per account (lockout)
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 120
    REFRESH_RATE_LIMIT_PER_MINUTE: int = 600
    FORGOT_PASSWORD_RATE_LIMIT_PER_HOUR: int = 20
    FORGOT_PASSWORD_IDENTIFIER_RATE_LIMIT_PER_HOUR: int = 5
    OTP_VERIFY_RATE_LIMIT_PER_MINUTE: int = 10
    RESET_PASSWORD_RATE_LIMIT_PER_MINUTE: int = 10
    EXPORT_RATE_LIMIT_PER_HOUR: int = 30

    # --- Export ---
    EXPORT_MAX_ROWS: int = Field(default=500_000, ge=1)
    EXPORT_BATCH_SIZE: int = Field(default=2_000, ge=100, le=10_000)

    # --- Housekeeping (python -m app.cli purge-expired) ---
    SESSION_RETENTION_DAYS: int = Field(default=30, ge=1, description="Keep ended sessions this long for audit")
    OUTBOX_RETENTION_DAYS: int = Field(default=7, ge=1)

    # --- Two-factor authentication (TOTP) ---
    MFA_ISSUER: str = "LMS"
    # TEST SERVERS ONLY: a fixed 6-digit code accepted as the two-factor code (besides the app's real codes), so testers
    # need no authenticator app. Refused outside local/test; leave unset everywhere else.
    MFA_TEST_CODE: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    # Roles that must enrol before they can use the API (they may still reach /users/me, logout and MFA set-up).
    MFA_REQUIRED_ROLES: list[str] = Field(default_factory=lambda: ["super_admin", "admin"])
    # Fernet key (32 url-safe base64 bytes) used to encrypt TOTP secrets at rest. Required outside local/test.
    MFA_ENCRYPTION_KEY: SecretStr | None = None
    MFA_CHALLENGE_EXPIRE_MINUTES: int = Field(default=5, ge=1, le=15)
    MFA_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=10)
    MFA_RECOVERY_CODE_COUNT: int = Field(default=10, ge=5, le=20)
    MFA_VERIFY_RATE_LIMIT_PER_MINUTE: int = 10

    # --- Bulk import ---
    IMPORT_MAX_ROWS: int = Field(default=5_000, ge=1, le=50_000)
    IMPORT_MAX_FILE_BYTES: int = Field(default=5 * 1024 * 1024, ge=1024)
    IMPORT_RATE_LIMIT_PER_HOUR: int = 20
    # Larger files go through POST /users/import-jobs and are processed by the worker.
    IMPORT_JOB_MAX_ROWS: int = Field(default=50_000, ge=1, le=500_000)
    IMPORT_JOB_MAX_FILE_BYTES: int = Field(default=50 * 1024 * 1024, ge=1024)

    # --- Background jobs & worker (python -m app.worker) ---
    JOB_STORAGE_DIR: Path = Path("var/jobs")
    EXPORT_FILE_TTL_HOURS: int = Field(default=72, ge=1, le=720)
    WORKER_POLL_SECONDS: float = Field(default=2.0, gt=0)
    WORKER_PURGE_INTERVAL_MINUTES: int = Field(default=60, ge=1)
    JOB_MAX_ATTEMPTS: int = Field(default=3, ge=1)
    FRONTEND_JOBS_PATH: str = "/downloads"

    # --- Events (transactional outbox relayed by the worker) ---
    EVENTS_STREAM: str = "lms:events"
    EVENTS_STREAM_MAX_LENGTH: int = Field(default=1_000_000, ge=1_000)
    OUTBOX_BATCH_SIZE: int = Field(default=500, ge=1, le=5_000)

    # --- Email ---
    EMAIL_BACKEND: Literal["console", "smtp"] = "console"
    EMAIL_FROM: str = "LMS <no-reply@lms.local>"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: SecretStr | None = None
    SMTP_STARTTLS: bool = True
    SMTP_USE_TLS: bool = False
    SMTP_TIMEOUT_SECONDS: int = 10

    @property
    def is_production_like(self) -> bool:
        return self.ENVIRONMENT in {"staging", "production"}

    @property
    def refresh_token_ttl_seconds(self) -> int:
        return self.REFRESH_TOKEN_EXPIRE_DAYS * 86400

    def frontend_url(self, path: str) -> str:
        return f"{self.FRONTEND_BASE_URL.rstrip('/')}{path}"

    @model_validator(mode="after")
    def validate_security(self) -> "Settings":
        errors: list[str] = []
        jwt_secret = self.JWT_SECRET_KEY.get_secret_value()
        token_secret = self.TOKEN_HASH_SECRET.get_secret_value()

        if self.JWT_ALGORITHM == "HS256" and self.ENVIRONMENT != "test":
            # every other service verifies access tokens with the published public key (RS256 only), so a shared
            # secret would lock the whole platform out of everything but user-management
            errors.append("JWT_ALGORITHM must be RS256 except in tests (run scripts/generate_jwt_keys.py keys/)")
        if self.JWT_ALGORITHM == "HS256" and len(jwt_secret) < 32:
            errors.append("JWT_SECRET_KEY must be at least 32 characters")
        if self.JWT_ALGORITHM == "RS256" and not (self.JWT_PRIVATE_KEY_FILE and self.JWT_PUBLIC_KEY_FILE):
            errors.append("RS256 requires JWT_PRIVATE_KEY_FILE and JWT_PUBLIC_KEY_FILE")
        if bool(self.JWT_PREVIOUS_PUBLIC_KEY_FILE) != bool(self.JWT_PREVIOUS_KEY_ID):
            errors.append("JWT_PREVIOUS_PUBLIC_KEY_FILE and JWT_PREVIOUS_KEY_ID must be set together")
        if self.JWT_PREVIOUS_KEY_ID and self.JWT_PREVIOUS_KEY_ID == self.JWT_KEY_ID:
            errors.append("JWT_PREVIOUS_KEY_ID must differ from JWT_KEY_ID")
        if len(token_secret) < 32:
            errors.append("TOKEN_HASH_SECRET must be at least 32 characters")

        if self.is_production_like:
            if self.DEBUG:
                errors.append("DEBUG must be false outside local/test")
            if self.EMAIL_BACKEND == "console":
                errors.append("EMAIL_BACKEND=console is not allowed outside local/test")
            if DEV_SECRET_MARKER in token_secret:
                errors.append("TOKEN_HASH_SECRET still uses the development default")
            if self.MFA_ENCRYPTION_KEY is None:
                errors.append("MFA_ENCRYPTION_KEY must be set outside local/test")
            if self.MFA_TEST_CODE:
                errors.append("MFA_TEST_CODE (a fixed two-factor code for testing) must not be set outside local/test")
            if DEV_SECRET_MARKER in self.INTERNAL_SERVICE_TOKEN.get_secret_value():
                errors.append("INTERNAL_SERVICE_TOKEN still uses the development default")
            if self.JWT_ALGORITHM != "RS256":
                errors.append(
                    "JWT_ALGORITHM must be RS256 outside local/test (other services verify tokens with the public key)"
                )
            if not self.REFRESH_COOKIE_SECURE:
                errors.append("REFRESH_COOKIE_SECURE must be true outside local/test")
            if "*" in self.TRUSTED_HOSTS:
                errors.append("TRUSTED_HOSTS must list explicit hosts outside local/test")

        if errors:
            raise ValueError("; ".join(errors))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
