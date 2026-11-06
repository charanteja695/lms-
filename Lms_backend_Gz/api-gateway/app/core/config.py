"""Service configuration.

Every setting is read from environment variables (or a local ``.env`` file). Development defaults exist only so the gateway boots locally;
``validate_security`` refuses to start staging/production with any of them.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Where each service listens on a developer's machine (see lms-backend/README.md). Docker overrides them all (UPSTREAM_URLS).
LOCAL_UPSTREAMS: dict[str, str] = {
    "user-management": "http://127.0.0.1:8001", "catalog-service": "http://127.0.0.1:8002", "media-service": "http://127.0.0.1:8003", "subscription-service": "http://127.0.0.1:8004",
    "learning-service": "http://127.0.0.1:8005", "code-execution-service": "http://127.0.0.1:8006", "assessment-service": "http://127.0.0.1:8007", "proctoring-service": "http://127.0.0.1:8008",
    "certificate-service": "http://127.0.0.1:8009", "ai-gateway": "http://127.0.0.1:8010", "ai-tutor-service": "http://127.0.0.1:8011", "support-service": "http://127.0.0.1:8012",
    "career-service": "http://127.0.0.1:8013", "job-portal-service": "http://127.0.0.1:8014", "ai-interview-service": "http://127.0.0.1:8015", "notification-service": "http://127.0.0.1:8016",
    "analytics-service": "http://127.0.0.1:8017", "billing-service": "http://127.0.0.1:8018",
}
ROUTES_FILE = Path(__file__).resolve().parents[2] / "config" / "routes.json"



def _private_or_https(url: str) -> bool:
    """https anywhere; plain http only to a private-network host: localhost, a loopback address, or a single-label
    container/service name such as ``user-management`` (resolvable only inside the deployment's own network)."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return parsed.scheme == "https" or (parsed.scheme == "http" and (host in {"localhost", "127.0.0.1", "::1"} or "." not in host))

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application ---
    APP_NAME: str = "lms-api-gateway"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["local", "test", "staging", "production"] = "local"
    DEBUG: bool = False
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_JSON: bool = True
    CORS_ORIGINS: list[str] = Field(default_factory=list, description="The browser origins allowed to call the platform. This is the only place CORS is applied: services' own CORS headers are dropped")
    TRUSTED_HOSTS: list[str] = Field(default_factory=lambda: ["*"])
    TRUST_PROXY_HEADERS: bool = Field(default=False, description="Believe X-Forwarded-For from the load balancer in front of the gateway (only behind one you control)")

    # --- Redis (rate limiting and the revocation state user-management publishes) ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Authentication: an Authorization header, if sent, must be valid; the services still verify it themselves ---
    USER_MANAGEMENT_JWKS_URL: str = "http://127.0.0.1:8001/.well-known/jwks.json"
    JWT_ISSUER: str = "lms-user-management"
    JWT_AUDIENCE: str = "lms"
    JWT_LEEWAY_SECONDS: int = Field(default=10, ge=0, le=60)
    JWKS_CACHE_SECONDS: int = Field(default=300, ge=10)
    JWKS_FETCH_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0)
    ACCESS_STATE_KEY_PREFIX: str = "lms:access"

    # --- Routing ---
    UPSTREAM_URLS: str = Field(default="", description="JSON object of service name -> base URL, overriding the local defaults for the services it names")
    MAX_BODY_BYTES: int = Field(default=5 * 1024 * 1024 * 1024, ge=1024, description="Larger request bodies are refused (spoken interview answers are the biggest legitimate ones)")
    UPSTREAM_CONNECT_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0)
    UPSTREAM_READ_TIMEOUT_SECONDS: float = Field(default=600.0, gt=0)
    STREAM_READ_TIMEOUT_SECONDS: float = Field(default=3600.0, gt=0, description="For server-sent-event streams (a path ending /stream)")
    HEALTH_CHECK_TIMEOUT_SECONDS: float = Field(default=2.0, gt=0)

    # --- Rate limiting: fixed one-minute windows, per user when a valid token is sent, per client IP otherwise ---
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_USER_PER_MINUTE: int = Field(default=600, ge=1)
    RATE_LIMIT_ANONYMOUS_PER_MINUTE: int = Field(default=120, ge=1)
    RATE_LIMIT_AUTH_PER_MINUTE: int = Field(default=600, ge=1, description="Per IP, for sign-in, token refresh and password-reset paths (/api/v1/auth); a school shares one IP")

    @property
    def is_production_like(self) -> bool:
        return self.ENVIRONMENT in {"staging", "production"}

    def upstreams(self) -> dict[str, str]:
        merged = dict(LOCAL_UPSTREAMS)
        if self.UPSTREAM_URLS:
            merged.update({name: url.rstrip("/") for name, url in json.loads(self.UPSTREAM_URLS).items()})
        return merged

    def validate_security(self) -> None:
        errors: list[str] = []
        if self.is_production_like:
            if self.DEBUG:
                errors.append("DEBUG must be false outside local/test")
            if "*" in self.TRUSTED_HOSTS:
                errors.append("TRUSTED_HOSTS must list explicit hosts outside local/test")
            if not self.CORS_ORIGINS:
                errors.append("CORS_ORIGINS must name the frontend's origin outside local/test")
            if not _private_or_https(self.USER_MANAGEMENT_JWKS_URL):
                errors.append("USER_MANAGEMENT_JWKS_URL must use https outside local/test")
        if self.UPSTREAM_URLS:
            try:
                parsed = json.loads(self.UPSTREAM_URLS)
                if not isinstance(parsed, dict) or not all(isinstance(v, str) for v in parsed.values()):
                    raise ValueError
            except ValueError:
                errors.append("UPSTREAM_URLS must be a JSON object of service name -> URL")
        if errors:
            raise ValueError("; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_security()
    return settings
