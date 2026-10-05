from httpx import AsyncClient

AUTHOR = ("content.author",)


async def _upload(client: AsyncClient, authed, *, context_type: str | None = None, context_id: str | None = None) -> dict:
    authed(scopes=AUTHOR)
    payload = {"original_filename": "clip.mp4", "content_type": "video/mp4", "byte_size": 1024}
    if context_type:
        payload["context_type"] = context_type
        payload["context_id"] = context_id
    response = await client.post("/api/v1/media/uploads", json=payload)
    return response.json()["asset"]


async def test_list_filters_by_context(client: AsyncClient, authed) -> None:
    await _upload(client, authed)
    tagged = await _upload(client, authed, context_type="course_version", context_id="1755000000009999")

    authed(scopes=())
    response = await client.get("/api/v1/media", params={"context_type": "course_version", "context_id": "1755000000009999"})
    assert response.status_code == 200
    body = response.json()
    assert body["page_context"]["total_records"] == 1
    assert body["assets"][0]["asset_id"] == tagged["asset_id"]


async def test_unknown_asset_is_404(client: AsyncClient, authed) -> None:
    authed(scopes=())
    response = await client.get("/api/v1/media/1755000000009998")
    assert response.status_code == 404
    assert response.json()["code"] == "MEDIA_ASSET_NOT_FOUND"
