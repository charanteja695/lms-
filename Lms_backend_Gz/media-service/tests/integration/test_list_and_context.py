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


async def test_library_filters_summary_and_restore(client: AsyncClient, authed) -> None:
    video = await _upload(client, authed)
    authed(scopes=AUTHOR)
    pdf = (
        await client.post(
            "/api/v1/media/uploads",
            json={"original_filename": "Week 1 notes.pdf", "content_type": "application/pdf", "byte_size": 2048},
        )
    ).json()["asset"]

    found = (await client.get("/api/v1/media", params={"kind": "document", "search": "week 1"})).json()["assets"]
    assert [a["asset_id"] for a in found] == [pdf["asset_id"]]
    assert (await client.get("/api/v1/media", params={"search": "100%"})).json()["assets"] == []

    summary = (await client.get("/api/v1/media/summary")).json()["summary"]
    assert {k["kind"]: k["count"] for k in summary["kinds"]} == {"video": 1, "document": 1}
    assert summary["archived"] == 0

    assert (await client.delete(f"/api/v1/media/{video['asset_id']}")).status_code == 200
    archived = (await client.get("/api/v1/media", params={"archived": "true"})).json()["assets"]
    assert [a["asset_id"] for a in archived] == [video["asset_id"]]
    assert (await client.get("/api/v1/media/summary")).json()["summary"]["archived"] == 1

    restored = await client.post(f"/api/v1/media/{video['asset_id']}/restore")
    assert restored.status_code == 200 and restored.json()["asset"]["archived_at"] is None

    authed(scopes=())
    assert (await client.get("/api/v1/media/summary")).status_code == 403
    assert (await client.post(f"/api/v1/media/{video['asset_id']}/restore")).status_code == 403
