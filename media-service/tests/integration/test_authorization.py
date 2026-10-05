from httpx import AsyncClient

UPLOAD_PAYLOAD = {"original_filename": "clip.mp4", "content_type": "video/mp4", "byte_size": 1024}


async def test_missing_token_is_rejected_without_any_network_call(client: AsyncClient) -> None:
    response = await client.post("/api/v1/media/uploads", json=UPLOAD_PAYLOAD)
    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_token_without_content_author_scope_is_forbidden(client: AsyncClient, authed) -> None:
    authed(scopes=())
    response = await client.post("/api/v1/media/uploads", json=UPLOAD_PAYLOAD)
    assert response.status_code == 403


async def test_token_with_content_author_scope_is_allowed(client: AsyncClient, authed) -> None:
    authed(scopes=("content.author",))
    response = await client.post("/api/v1/media/uploads", json=UPLOAD_PAYLOAD)
    assert response.status_code == 201
