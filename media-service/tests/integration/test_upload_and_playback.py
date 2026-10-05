import boto3
from httpx import AsyncClient

from app.events.consumers.pipeline_events import handle_media_uploaded
from tests.conftest import TEST_BUCKET, _settings

AUTHOR = ("content.author",)
UPLOAD_PAYLOAD = {"original_filename": "clip.mp4", "content_type": "video/mp4", "byte_size": 1024}


async def _start_upload(client: AsyncClient, authed) -> dict:
    authed(scopes=AUTHOR)
    response = await client.post("/api/v1/media/uploads", json=UPLOAD_PAYLOAD)
    assert response.status_code == 201, response.text
    return response.json()


async def _put_fake_object(fields: dict) -> None:
    boto3.client("s3", region_name="us-east-1").put_object(
        Bucket=TEST_BUCKET, Key=fields["key"], Body=b"fake video bytes", ContentType="video/mp4"
    )


async def _run_worker_transcode(app, asset_public_id: str) -> None:
    """Simulates what ``python -m app.worker`` does on receiving ``media.uploaded``."""
    async with app.state.sessionmaker() as db:
        await handle_media_uploaded(db, _settings(), {"media_asset_id": asset_public_id})


async def test_reject_unsupported_content_type(client: AsyncClient, authed) -> None:
    authed(scopes=AUTHOR)
    response = await client.post(
        "/api/v1/media/uploads", json={"original_filename": "doc.pdf", "content_type": "application/pdf", "byte_size": 10}
    )
    assert response.status_code == 400
    assert response.json()["code"] == "UNSUPPORTED_CONTENT_TYPE"


async def test_reject_oversized_upload(client: AsyncClient, authed) -> None:
    authed(scopes=AUTHOR)
    response = await client.post(
        "/api/v1/media/uploads",
        json={"original_filename": "clip.mp4", "content_type": "video/mp4", "byte_size": 6 * 1024 * 1024 * 1024},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "FILE_TOO_LARGE"


async def test_complete_before_object_exists_fails(client: AsyncClient, authed) -> None:
    body = await _start_upload(client, authed)
    asset_id = body["asset"]["asset_id"]

    authed(scopes=AUTHOR)
    response = await client.post(f"/api/v1/media/{asset_id}/complete")
    assert response.status_code == 400
    assert response.json()["code"] == "UPLOAD_NOT_FOUND"


async def test_complete_marks_video_uploaded_not_ready(client: AsyncClient, authed) -> None:
    """A video needs the worker's transcoder before it's playable (see test_worker_transcodes_video_to_ready)."""
    body = await _start_upload(client, authed)
    asset_id = body["asset"]["asset_id"]
    await _put_fake_object(body["upload"]["fields"])

    authed(scopes=AUTHOR)
    response = await client.post(f"/api/v1/media/{asset_id}/complete")
    assert response.status_code == 200, response.text
    asset = response.json()["asset"]
    assert asset["status"] == "uploaded"
    assert asset["byte_size"] == len(b"fake video bytes")
    assert asset["renditions"] == []

    response = await client.post(f"/api/v1/media/{asset_id}/complete")
    assert response.status_code == 400
    assert response.json()["code"] == "UPLOAD_ALREADY_COMPLETED"


async def test_image_upload_is_ready_immediately_no_transcode(client: AsyncClient, authed) -> None:
    authed(scopes=AUTHOR)
    response = await client.post(
        "/api/v1/media/uploads", json={"original_filename": "cover.jpg", "content_type": "image/jpeg", "byte_size": 200}
    )
    body = response.json()
    boto3.client("s3", region_name="us-east-1").put_object(
        Bucket=TEST_BUCKET, Key=body["upload"]["fields"]["key"], Body=b"fake jpeg bytes"
    )

    authed(scopes=AUTHOR)
    response = await client.post(f"/api/v1/media/{body['asset']['asset_id']}/complete")
    asset = response.json()["asset"]
    assert asset["status"] == "ready"
    assert [r["label"] for r in asset["renditions"]] == ["source"]


async def test_worker_transcodes_video_to_ready_and_deletes_the_original(client: AsyncClient, authed, app, stub_ffmpeg) -> None:
    body = await _start_upload(client, authed)
    asset_id = body["asset"]["asset_id"]
    original_key = body["upload"]["fields"]["key"]
    await _put_fake_object(body["upload"]["fields"])

    authed(scopes=AUTHOR)
    await client.post(f"/api/v1/media/{asset_id}/complete")

    await _run_worker_transcode(app, asset_id)

    response = await client.get(f"/api/v1/media/{asset_id}")
    asset = response.json()["asset"]
    assert asset["status"] == "ready"
    assert asset["duration_seconds"] == 90
    assert {r["label"] for r in asset["renditions"]} == {"720p", "480p"}  # capped at the (stubbed) 720p source

    # the raw original is deleted once compressed renditions exist (the whole point: cost)
    s3 = boto3.client("s3", region_name="us-east-1")
    existing_keys = {obj["Key"] for obj in s3.list_objects_v2(Bucket=TEST_BUCKET).get("Contents", [])}
    assert original_key not in existing_keys


async def test_playback_token_requires_a_ready_asset(client: AsyncClient, authed) -> None:
    body = await _start_upload(client, authed)
    asset_id = body["asset"]["asset_id"]

    authed(scopes=())  # any authenticated viewer can request a token
    response = await client.post(f"/api/v1/media/{asset_id}/playback-tokens")
    assert response.status_code == 400
    assert response.json()["code"] == "MEDIA_ASSET_NOT_READY"


async def test_playback_token_resolves_to_a_signed_url(client: AsyncClient, authed, app, stub_ffmpeg) -> None:
    body = await _start_upload(client, authed)
    asset_id = body["asset"]["asset_id"]
    await _put_fake_object(body["upload"]["fields"])
    authed(scopes=AUTHOR)
    await client.post(f"/api/v1/media/{asset_id}/complete")
    await _run_worker_transcode(app, asset_id)

    authed(scopes=())
    response = await client.post(f"/api/v1/media/{asset_id}/playback-tokens")
    assert response.status_code == 201
    token = response.json()["playback"]["token"]

    response = await client.get(f"/api/v1/playback/{token}", follow_redirects=False)
    assert response.status_code == 307
    assert TEST_BUCKET in response.headers["location"]


async def test_unknown_playback_token_is_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/playback/does-not-exist", follow_redirects=False)
    assert response.status_code == 404
    assert response.json()["code"] == "PLAYBACK_TOKEN_NOT_FOUND"


async def test_archiving_an_asset_stops_new_playback_tokens(client: AsyncClient, authed, app, stub_ffmpeg) -> None:
    body = await _start_upload(client, authed)
    asset_id = body["asset"]["asset_id"]
    await _put_fake_object(body["upload"]["fields"])
    authed(scopes=AUTHOR)
    await client.post(f"/api/v1/media/{asset_id}/complete")
    await _run_worker_transcode(app, asset_id)

    response = await client.delete(f"/api/v1/media/{asset_id}")
    assert response.status_code == 200
    assert response.json()["asset"]["archived_at"] is not None

    authed(scopes=())
    response = await client.post(f"/api/v1/media/{asset_id}/playback-tokens")
    assert response.status_code == 400
    assert response.json()["code"] == "MEDIA_ASSET_NOT_READY"
