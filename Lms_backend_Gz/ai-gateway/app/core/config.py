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
    APP_NAME: str = "lms-ai-gateway"
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
    DATABASE_URL: str = "postgresql+asyncpg://lms:lms@localhost:5432/lms_ai_gateway"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT_SECONDS: int = 30
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_ECHO: bool = False
    DB_STATEMENT_TIMEOUT_MS: int = Field(default=15_000, ge=100)

    # --- Redis (rate limiting, access-state reads, event stream, idempotency cache) ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Authentication: this service only verifies tokens, it never issues them. The admin API (prompts,
    # quotas, logs, model routing) is used by people; the completion/embedding/speech API is used by other
    # services, authenticated with INTERNAL_SERVICE_TOKEN instead (see app/api/deps.py). ---
    USER_MANAGEMENT_JWKS_URL: str = "http://localhost:8001/.well-known/jwks.json"
    JWT_ISSUER: str = "lms-user-management"
    JWT_AUDIENCE: str = "lms"
    JWT_LEEWAY_SECONDS: int = Field(default=10, ge=0, le=60)
    JWKS_CACHE_SECONDS: int = Field(default=300, ge=10)
    JWKS_FETCH_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0)
    ACCESS_STATE_KEY_PREFIX: str = "lms:access"
    INTERNAL_SERVICE_TOKEN: SecretStr = SecretStr(f"{DEV_SECRET_MARKER}-internal-service-token-change-me-0")

    # --- Rate limits ---
    RATE_LIMIT_ENABLED: bool = True
    ADMIN_RATE_LIMIT_PER_HOUR: int = Field(default=600, ge=1)
    COMPLETION_RATE_LIMIT_PER_ORG_PER_MINUTE: int = Field(default=120, ge=1)
    EMBEDDING_RATE_LIMIT_PER_ORG_PER_MINUTE: int = Field(default=120, ge=1)

    # --- Events (transactional outbox relayed by the worker; consumed from lms:events) ---
    EVENTS_STREAM: str = "lms:events"
    EVENTS_STREAM_MAX_LENGTH: int = Field(default=1_000_000, ge=1_000)
    OUTBOX_BATCH_SIZE: int = Field(default=500, ge=1, le=5_000)
    EVENTS_CONSUMER_GROUP: str = "ai-gateway"
    EVENTS_CONSUMER_NAME: str = "worker-1"
    EVENTS_BLOCK_MS: int = Field(default=5_000, ge=100)
    PROCESSED_EVENTS_RETENTION_DAYS: int = Field(default=14, ge=1)
    WORKER_POLL_SECONDS: float = Field(default=2.0, gt=0)
    HOUSEKEEPING_INTERVAL_SECONDS: float = Field(default=3600.0, gt=0)

    # --- Providers. Real HTTP clients (app/providers/), never exercised against the network in this
    # environment — see README "Not exercised". Unset an API key and that provider's capability answers
    # PROVIDER_NOT_CONFIGURED instead of failing every call. ---
    ANTHROPIC_API_KEY: SecretStr | None = None
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
    ANTHROPIC_VERSION: str = "2023-06-01"
    ANTHROPIC_DEFAULT_MODEL: str = "claude-sonnet-5-5"
    ANTHROPIC_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0)
    VOYAGE_API_KEY: SecretStr | None = None
    VOYAGE_BASE_URL: str = "https://api.voyageai.com"
    VOYAGE_DEFAULT_MODEL: str = "voyage-3"
    VOYAGE_TIMEOUT_SECONDS: float = Field(default=15.0, gt=0)
    # Speech (STT/TTS): no provider is wired up yet (needed only by the phase-10 AI interviewer). The routing
    # contract exists (app/providers/speech.py); every call answers PROVIDER_NOT_CONFIGURED until one is.
    STT_PROVIDER_URL: str | None = None
    TTS_PROVIDER_URL: str | None = None

    # --- Policy clamps applied to every call regardless of what the caller asks for ---
    MAX_TOKENS_PER_CALL: int = Field(default=4_096, ge=1, le=100_000)
    MAX_MESSAGES_PER_CALL: int = Field(default=64, ge=1, le=1_000)
    MAX_TEXTS_PER_EMBEDDING_CALL: int = Field(default=100, ge=1, le=2_000)
    DEFAULT_TEMPERATURE: float = Field(default=0.7, ge=0, le=2)
    PROVIDER_MAX_RETRIES: int = Field(default=1, ge=0, le=5)  # per provider, before falling back to the next one

    # --- Guardrails: a small, explicit keyword blocklist — not an ML moderation model. Extend or replace
    # this behind the same interface (app/guardrails/moderation.py) when a real one is available. ---
    MODERATION_BLOCKLIST: list[str] = Field(
        default_factory=lambda: ["how to make a bomb", "kill myself", "child sexual abuse material"]
    )

    # --- Quotas: an org without its own app/models/quota.py::OrgQuota row uses these platform defaults
    # (see app/services/quota_service.py). Cost is tracked, not billed, until billing-service exists. ---
    DEFAULT_MONTHLY_TOKEN_LIMIT: int = Field(default=5_000_000, ge=0)
    DEFAULT_MONTHLY_REQUEST_LIMIT: int = Field(default=50_000, ge=0)
    DEFAULT_MONTHLY_BUDGET_CENTS: int = Field(default=50_000, ge=0)  # $500

    # --- Idempotency (Redis, not Postgres: a completion's content is cached only long enough to answer a
    # client's retry, never kept as a second long-lived copy of model output) ---
    IDEMPOTENCY_RETENTION_HOURS: int = Field(default=24, ge=1, le=168)

    # --- Audit log retention ---
    CALL_LOG_RETENTION_DAYS: int = Field(default=90, ge=1)

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
