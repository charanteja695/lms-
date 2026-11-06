"""Real client for Voyage AI's embeddings API — Anthropic's recommended embedding partner (Anthropic has no
first-party embeddings endpoint; docs/PRODUCT.md decision D5: "embeddings + pgvector").

Same caveat as app/providers/anthropic.py: written against the documented request/response shape
(POST /v1/embeddings, OpenAI-compatible body and response), not exercised against the real network here.
"""

from typing import Any

import httpx

from app.core.config import Settings
from app.providers.base import EmbeddingProvider, EmbedRequest, EmbedResult, ProviderCallError


class VoyageProvider(EmbeddingProvider):
    name = "voyage"

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        api_key = self.settings.VOYAGE_API_KEY
        return httpx.AsyncClient(
            base_url=self.settings.VOYAGE_BASE_URL.rstrip("/"),
            timeout=self.settings.VOYAGE_TIMEOUT_SECONDS,
            transport=self._transport,
            headers={"Authorization": f"Bearer {api_key.get_secret_value() if api_key else ''}", "content-type": "application/json"},
        )

    async def embed(self, request: EmbedRequest) -> EmbedResult:
        try:
            async with self._client() as client:
                response = await client.post("/v1/embeddings", json={"model": request.model, "input": request.texts})
        except httpx.HTTPError as exc:
            raise ProviderCallError(f"voyage unreachable: {exc.__class__.__name__}") from exc
        if response.status_code >= 400:
            raise ProviderCallError(f"voyage answered {response.status_code}: {response.text[:280]}")
        data: dict[str, Any] = response.json()
        by_index = sorted(data.get("data", []), key=lambda row: row.get("index", 0))
        return EmbedResult(
            vectors=[row["embedding"] for row in by_index],
            model=data.get("model", request.model),
            tokens=int(data.get("usage", {}).get("total_tokens", 0)),
        )
