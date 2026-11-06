from app.providers.base import ProviderCallError
from tests.conftest import ORG_A, USER


def _body(**overrides):
    base = {"organization_id": str(ORG_A), "service": "ai-tutor-service", "user_id": str(USER), "texts": ["What is recursion?", "Explain a stack."]}
    base.update(overrides)
    return base


async def test_embeddings_are_returned_in_request_order(client, fake_embedding, internal_headers):
    response = await client.post("/api/v1/internal/embeddings", json=_body(), headers=internal_headers)
    assert response.status_code == 200
    body = response.json()["embedding"]
    assert len(body["vectors"]) == 2 and body["provider"] == "voyage"


async def test_pii_is_redacted_before_reaching_the_embedding_provider(client, fake_embedding, internal_headers):
    response = await client.post("/api/v1/internal/embeddings", json=_body(texts=["contact me at a@b.com"]), headers=internal_headers)
    assert response.status_code == 200
    assert "a@b.com" not in fake_embedding.calls[0].texts[0]


async def test_without_the_internal_token_the_call_is_refused(client):
    response = await client.post("/api/v1/internal/embeddings", json=_body())
    assert response.status_code == 403


async def test_a_provider_failure_returns_502_and_refunds(client, fake_embedding, internal_headers):
    fake_embedding.queue_error(ProviderCallError("down"))
    response = await client.post("/api/v1/internal/embeddings", json=_body(), headers=internal_headers)
    assert response.status_code == 502


async def test_an_idempotency_key_replays_without_a_second_provider_call(client, fake_embedding, internal_headers):
    headers = {**internal_headers, "Idempotency-Key": "embed-retry-1"}
    first = await client.post("/api/v1/internal/embeddings", json=_body(), headers=headers)
    second = await client.post("/api/v1/internal/embeddings", json=_body(), headers=headers)
    assert first.json()["embedding"]["call_id"] == second.json()["embedding"]["call_id"]
    assert len(fake_embedding.calls) == 1


async def test_too_many_texts_is_a_422(client, internal_headers):
    response = await client.post("/api/v1/internal/embeddings", json=_body(texts=["x"] * 101), headers=internal_headers)
    assert response.status_code == 422
