import json
import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import fakeredis.aioredis
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from jwt.algorithms import RSAAlgorithm
from lms_common.auth import JWKSVerifier

from app.core.config import LOCAL_UPSTREAMS, Settings
from app.main import create_app

ISSUER, AUDIENCE, KID = "lms-user-management", "lms", "test-key-1"
USER, OTHER_USER, SUPER = 1755000000300001, 1755000000300002, 1755000000300003
ORG = 1755000000300011
API = "/api/v1"


def _key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


SIGNING_KEY, OTHER_KEY = _key(), _key()


def _jwks() -> dict[str, Any]:
    jwk = json.loads(RSAAlgorithm.to_jwk(SIGNING_KEY.public_key()))
    return {"keys": [{**jwk, "kid": KID, "alg": "RS256", "use": "sig"}]}


def make_token(*, user_id: int = USER, role: str = "student", org: int | None = ORG, session: int = 1755000000300900, version: int = 0, expires_in: int = 900, key: Any = None, kind: str = "access") -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "iss": ISSUER, "aud": AUDIENCE, "sub": str(user_id), "sid": str(session), "role": role, "ver": version, "jti": uuid.uuid4().hex, "type": kind, "iat": now, "nbf": now, "exp": now + expires_in,
    }
    if org:
        payload["org"] = str(org)
    return jwt.encode(payload, key or SIGNING_KEY, algorithm="RS256", headers={"kid": KID})


def bearer(**kwargs: Any) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(**kwargs)}"}


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {"ENVIRONMENT": "test", "LOG_JSON": False, "REDIS_URL": "redis://localhost:6379/15", "JWT_ISSUER": ISSUER, "JWT_AUDIENCE": AUDIENCE}
    values.update(overrides)
    return Settings(**values)


class Upstreams:
    """Stands in for every service: records what reached it and answers as scripted. ``service`` is found from the port in LOCAL_UPSTREAMS."""

    PORTS = {url.rsplit(":", 1)[1]: name for name, url in LOCAL_UPSTREAMS.items()}

    def __init__(self) -> None:
        self.requests: list[tuple[str, httpx.Request, bytes]] = []
        self.responder: Callable[[str, httpx.Request], httpx.Response] | None = None
        self.down: set[str] = set()
        self.timeout: set[str] = set()

    async def handler(self, request: httpx.Request) -> httpx.Response:
        body = b"".join([chunk async for chunk in request.stream]) if isinstance(request.stream, httpx.AsyncByteStream) else request.read()
        service = self.PORTS[str(request.url.port)]
        if service in self.down:
            raise httpx.ConnectError("refused", request=request)
        if service in self.timeout:
            raise httpx.ReadTimeout("slow", request=request)
        self.requests.append((service, request, body))
        if request.url.path.endswith("/health/live"):
            return httpx.Response(200, json={"status": "ok"})
        if self.responder:
            return self.responder(service, request)
        return httpx.Response(200, json={"status": "success", "service": service, "path": request.url.path})

    @property
    def last(self) -> tuple[str, httpx.Request, bytes]:
        return self.requests[-1]


@pytest.fixture
def upstreams() -> Upstreams:
    return Upstreams()


@pytest.fixture
async def redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
def make_app(upstreams, redis, monkeypatch):
    """Builds a gateway wired to the fake services, fakeredis and a verifier that trusts the test signing key."""

    async def fetch() -> dict[str, Any]:
        return _jwks()

    verifier = JWKSVerifier(issuer=ISSUER, audience=AUDIENCE, fetch_jwks=fetch)
    monkeypatch.setattr("app.api.proxy.get_verifier", lambda: verifier)

    def build(**overrides: Any):
        app = create_app(_settings(**overrides))
        app.state.redis = redis
        app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(upstreams.handler), follow_redirects=False)
        return app

    return build


@pytest.fixture
async def client(make_app) -> AsyncIterator[AsyncClient]:
    app = make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://gateway.test") as c:
        yield c
