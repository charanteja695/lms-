"""Service configuration.

Every setting is read from environment variables (or a local ``.env`` file).
Development defaults exist only so the service boots locally; ``validate_security``
refuses to start staging/production with any of them.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_MARKER = "insecure-dev"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application ---
    APP_NAME: str = "lms-ai-tutor-service"
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
    DATABASE_URL: str = "postgresql+asyncpg://lms:lms@localhost:5432/lms_ai_tutor"
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

    # --- Other services this one calls (synchronously, with the shared internal token) ---
    AI_GATEWAY_URL: str = "http://localhost:8010"
    AI_GATEWAY_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0)
    SUPPORT_SERVICE_URL: str = "http://localhost:8012"
    SUPPORT_SERVICE_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0)
    # Content indexing has no student behind it, so its embedding calls are billed to this organization in
    # ai-gateway's per-org quotas (a platform-owned id; give it its own quota row there).
    PLATFORM_ORGANIZATION_ID: int = Field(default=1755000000000001, ge=1)

    # --- Prompts registered in ai-gateway's prompt registry (see `python -m app.cli register-prompts`) ---
    LEARNING_PROMPT_KEY: str = "tutor.learning"
    SUPPORT_PROMPT_KEY: str = "tutor.support"
    SUMMARY_PROMPT_KEY: str = "tutor.escalation_summary"

    # --- Rate limits ---
    RATE_LIMIT_ENABLED: bool = True
    MESSAGE_RATE_LIMIT_PER_USER_PER_MINUTE: int = Field(default=12, ge=1)
    CONVERSATION_RATE_LIMIT_PER_USER_PER_HOUR: int = Field(default=30, ge=1)
    AUTHORING_RATE_LIMIT_PER_HOUR: int = Field(default=300, ge=1)

    # --- Events (transactional outbox relayed by the worker; consumed from lms:events) ---
    EVENTS_STREAM: str = "lms:events"
    EVENTS_STREAM_MAX_LENGTH: int = Field(default=1_000_000, ge=1_000)
    OUTBOX_BATCH_SIZE: int = Field(default=500, ge=1, le=5_000)
    EVENTS_CONSUMER_GROUP: str = "ai-tutor-service"
    EVENTS_CONSUMER_NAME: str = "worker-1"
    EVENTS_BLOCK_MS: int = Field(default=5_000, ge=100)
    PROCESSED_EVENTS_RETENTION_DAYS: int = Field(default=14, ge=1)
    WORKER_POLL_SECONDS: float = Field(default=2.0, gt=0)
    HOUSEKEEPING_INTERVAL_SECONDS: float = Field(default=3600.0, gt=0)

    # --- Retrieval (RAG). Vectors are stored as JSON and compared in-process (numpy) over one course version's
    # chunks — fine for a course (hundreds to low thousands of chunks); pgvector is the next step (D5). ---
    CHUNK_MAX_CHARS: int = Field(default=1_200, ge=200, le=8_000)
    TRANSCRIPT_WINDOW_SECONDS: int = Field(default=60, ge=10, le=600)
    RETRIEVAL_TOP_K: int = Field(default=5, ge=1, le=20)
    # Cosine similarity below which a chunk is not shown to the model or cited.
    MIN_RELEVANCE: float = Field(default=0.30, ge=0, le=1)
    # A top score under this is "low confidence" (docs/PRODUCT.md §5.5): no grounded answer is attempted.
    LOW_CONFIDENCE_BELOW: float = Field(default=0.35, ge=0, le=1)
    # A published FAQ answer at or above this is returned as-is, without calling a model at all.
    FAQ_DIRECT_ANSWER_AT: float = Field(default=0.90, ge=0, le=1)
    EMBED_BATCH_SIZE: int = Field(default=32, ge=1, le=100)
    INDEX_CACHE_VERSIONS: int = Field(default=64, ge=1)

    # --- Conversation behaviour ---
    HISTORY_MESSAGES: int = Field(default=10, ge=0, le=50)
    HISTORY_MAX_CHARS: int = Field(default=6_000, ge=500)
    MAX_MESSAGE_CHARS: int = Field(default=4_000, ge=100)
    MAX_CODE_CHARS: int = Field(default=8_000, ge=100)
    MAX_TOKENS: int = Field(default=800, ge=50, le=4_096)
    # Consecutive "could not ground this" answers in one conversation before it is escalated to a person.
    LOW_CONFIDENCE_ESCALATE_AFTER: int = Field(default=2, ge=1)
    # A graded attempt blocks the tutor until it is submitted, or its deadline plus this grace has passed
    # (so a lost attempt.submitted event cannot leave a student locked out).
    TEST_BLOCK_GRACE_SECONDS: int = Field(default=300, ge=0)
    # Hint ladder for practice problems: 1 nudge, 2 approach, 3 pseudocode, 4 solution (only after 3 hints).
    MAX_HINT_LEVEL: int = Field(default=4, ge=2, le=6)
    CONVERSATION_RETENTION_DAYS: int = Field(default=180, ge=1)

    # --- Escalation delivery to support-service (durable: retried with backoff by the worker) ---
    ESCALATION_BATCH_SIZE: int = Field(default=20, ge=1, le=200)
    ESCALATION_LEASE_SECONDS: int = Field(default=60, ge=10)
    ESCALATION_MAX_ATTEMPTS: int = Field(default=8, ge=1, le=30)
    SUMMARY_MESSAGES: int = Field(default=12, ge=1, le=50)

    # --- Indexing jobs ---
    INDEX_BATCH_SIZE: int = Field(default=5, ge=1, le=50)
    INDEX_LEASE_SECONDS: int = Field(default=300, ge=10)
    INDEX_MAX_ATTEMPTS: int = Field(default=6, ge=1, le=30)

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
            if DEV_SECRET_MARKER in self.INTERNAL_SERVICE_TOKEN.get_secret_value():
                errors.append("INTERNAL_SERVICE_TOKEN still uses the development default")
        if errors:
            raise ValueError("; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_security()
    return settings
