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
    APP_NAME: str = "lms-media-service"
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
    DATABASE_URL: str = "postgresql+asyncpg://lms:lms@localhost:5432/lms_media"
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

    # --- Hashing: server-side pepper used to HMAC opaque playback tokens at rest ---
    TOKEN_HASH_SECRET: SecretStr = SecretStr(f"{DEV_SECRET_MARKER}-token-hash-secret-change-me-0")

    # --- Rate limiting (per client IP unless stated) ---
    RATE_LIMIT_ENABLED: bool = True
    UPLOAD_URL_RATE_LIMIT_PER_HOUR: int = 60
    PLAYBACK_TOKEN_RATE_LIMIT_PER_MINUTE: int = 60

    # --- Events (transactional outbox relayed by the worker; consumed from lms:events) ---
    EVENTS_STREAM: str = "lms:events"
    EVENTS_STREAM_MAX_LENGTH: int = Field(default=1_000_000, ge=1_000)
    OUTBOX_BATCH_SIZE: int = Field(default=500, ge=1, le=5_000)
    EVENTS_CONSUMER_GROUP: str = "media-service"
    EVENTS_CONSUMER_NAME: str = "worker-1"
    EVENTS_BLOCK_MS: int = Field(default=5_000, ge=100)

    # --- Background worker (python -m app.worker: outbox relay + processing + inbound consumer) ---
    WORKER_POLL_SECONDS: float = Field(default=2.0, gt=0)

    # --- AWS S3 (the only storage backend this service targets) ---
    AWS_REGION: str = "ap-south-1"
    AWS_ACCESS_KEY_ID: SecretStr | None = None
    AWS_SECRET_ACCESS_KEY: SecretStr | None = None
    S3_BUCKET: str = "lms-media-dev"
    # Set only for local testing against a non-AWS S3-compatible endpoint (e.g. moto server);
    # leave unset in staging/production so boto3 talks to real AWS S3.
    S3_ENDPOINT_URL: str | None = None
    S3_UPLOAD_URL_EXPIRES_SECONDS: int = Field(default=900, ge=60, le=3_600)
    S3_PLAYBACK_URL_EXPIRES_SECONDS: int = Field(default=300, ge=30, le=3_600)

    # --- Upload rules ---
    MAX_UPLOAD_BYTES: int = Field(default=5 * 1024 * 1024 * 1024, ge=1024)  # 5 GiB
    ALLOWED_VIDEO_CONTENT_TYPES: list[str] = Field(
        default_factory=lambda: ["video/mp4", "video/quicktime", "video/webm", "video/x-matroska"]
    )
    ALLOWED_IMAGE_CONTENT_TYPES: list[str] = Field(default_factory=lambda: ["image/jpeg", "image/png", "image/webp"])

    # --- Playback ---
    PLAYBACK_TOKEN_EXPIRE_MINUTES: int = Field(default=240, ge=1, le=1_440)

    @property
    def is_production_like(self) -> bool:
        return self.ENVIRONMENT in {"staging", "production"}

    def validate_security(self) -> None:
        errors: list[str] = []
        token_secret = self.TOKEN_HASH_SECRET.get_secret_value()
        if len(token_secret) < 32:
            errors.append("TOKEN_HASH_SECRET must be at least 32 characters")
        if self.is_production_like:
            if self.DEBUG:
                errors.append("DEBUG must be false outside local/test")
            if "*" in self.TRUSTED_HOSTS:
                errors.append("TRUSTED_HOSTS must list explicit hosts outside local/test")
            if not _private_or_https(self.USER_MANAGEMENT_JWKS_URL):
                errors.append("USER_MANAGEMENT_JWKS_URL must use https outside local/test")
            if DEV_SECRET_MARKER in token_secret:
                errors.append("TOKEN_HASH_SECRET still uses the development default")
            if self.AWS_ACCESS_KEY_ID is None or self.AWS_SECRET_ACCESS_KEY is None:
                errors.append("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required outside local/test")
            if self.S3_ENDPOINT_URL is not None and not self.S3_ENDPOINT_URL.startswith("https://"):
                errors.append("S3_ENDPOINT_URL must be unset (AWS S3) or an https URL (S3-compatible storage) outside local/test")
            if self.S3_BUCKET == "lms-media-dev":
                errors.append("S3_BUCKET still uses the development default")
        if errors:
            raise ValueError("; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_security()
    return settings
