import boto3
import pytest
from moto import mock_aws

from tests.conftest import STUDENT, STUDENT_2

API = "/api/v1"


@pytest.fixture
def s3_bucket(settings):
    with mock_aws():
        client = boto3.client("s3", region_name=settings.AWS_REGION, aws_access_key_id="testing", aws_secret_access_key="testing")
        client.create_bucket(Bucket=settings.S3_BUCKET, CreateBucketConfiguration={"LocationConstraint": settings.AWS_REGION})
        yield client


async def _upload(client, s3_bucket, settings, filename: str = "Screen shot.png", body: bytes = b"\x89PNG data") -> dict:
    issued = await client.post(f"{API}/attachments/upload-url", json={"filename": filename, "content_type": "image/png", "size_bytes": len(body)})
    assert issued.status_code == 200, issued.text
    key = issued.json()["attachment"]["key"]
    s3_bucket.put_object(Bucket=settings.S3_BUCKET, Key=key, Body=body, ContentType="image/png")
    return {"key": key, "filename": filename}


async def test_a_student_attaches_a_screenshot_and_support_downloads_it(client, who, s3_bucket, settings):
    who.student()
    shot = await _upload(client, s3_bucket, settings)
    assert shot["key"].startswith(f"support/{STUDENT}/") and shot["key"].endswith("/Screen_shot.png")
    created = await client.post(f"{API}/tickets", json={"subject": "Video will not play", "description": "See the screenshot", "category": "technical", "attachments": [shot]})
    assert created.status_code == 201, created.text
    ticket_id = created.json()["ticket"]["ticket_id"]

    detail = (await client.get(f"{API}/tickets/{ticket_id}")).json()
    first = detail["messages"][0]
    assert first["attachments"] == [{"filename": "Screen shot.png", "content_type": "image/png", "size_bytes": 9}]
    link = (await client.get(f"{API}/tickets/{ticket_id}/messages/{first['message_id']}/attachments/0")).json()["attachment"]
    assert link["filename"] == "Screen shot.png" and shot["key"] in link["url"]
    assert (await client.get(f"{API}/tickets/{ticket_id}/messages/{first['message_id']}/attachments/1")).status_code == 404

    who.support()
    agent_link = await client.get(f"{API}/agent/tickets/{ticket_id}/messages/{first['message_id']}/attachments/0")
    assert agent_link.status_code == 200, agent_link.text
    who.student(STUDENT_2)  # someone else's ticket: not even its existence
    assert (await client.get(f"{API}/tickets/{ticket_id}/messages/{first['message_id']}/attachments/0")).status_code == 404


async def test_attachments_must_be_your_own_finished_upload_of_an_allowed_type(client, who, s3_bucket, settings):
    who.student()
    bad_type = await client.post(f"{API}/attachments/upload-url", json={"filename": "run.exe", "content_type": "application/x-msdownload", "size_bytes": 10})
    assert bad_type.status_code == 422 and bad_type.json()["details"][0]["code"] == "INVALID_FILE_TYPE"
    too_big = await client.post(f"{API}/attachments/upload-url", json={"filename": "a.png", "content_type": "image/png", "size_bytes": settings.ATTACHMENT_MAX_MB * 1024 * 1024 + 1})
    assert too_big.status_code == 422

    issued = (await client.post(f"{API}/attachments/upload-url", json={"filename": "a.png", "content_type": "image/png", "size_bytes": 5})).json()["attachment"]
    payload = {"subject": "Not uploaded yet", "description": "x", "category": "technical", "attachments": [{"key": issued["key"], "filename": "a.png"}]}
    missing = await client.post(f"{API}/tickets", json=payload)
    assert missing.status_code == 422 and missing.json()["details"][0]["code"] == "FILE_NOT_UPLOADED"

    who.student(STUDENT_2)
    theirs = await _upload(client, s3_bucket, settings)
    who.student()
    stolen = await client.post(f"{API}/tickets", json={**payload, "attachments": [theirs]})
    assert stolen.status_code == 422 and stolen.json()["details"][0]["code"] == "NOT_YOUR_FILE"

    many = [await _upload(client, s3_bucket, settings, f"s{i}.png") for i in range(settings.ATTACHMENT_MAX_FILES + 1)]
    too_many = await client.post(f"{API}/tickets", json={**payload, "attachments": many})
    assert too_many.status_code == 422 and too_many.json()["details"][0]["code"] == "TOO_MANY_FILES"


async def test_an_internal_note_attachment_is_never_reachable_by_the_student(client, who, s3_bucket, settings):
    who.student()
    ticket_id = (await client.post(f"{API}/tickets", json={"subject": "Payment failed", "description": "twice", "category": "billing"})).json()["ticket"]["ticket_id"]
    who.support()
    log = await _upload(client, s3_bucket, settings, "gateway.log")
    note = await client.post(f"{API}/agent/tickets/{ticket_id}/replies", json={"body": "Gateway log", "internal": True, "attachments": [log]})
    assert note.status_code == 201, note.text
    note_id = note.json()["reply"]["message_id"]
    assert note.json()["reply"]["attachments"][0]["filename"] == "gateway.log"
    assert (await client.get(f"{API}/agent/tickets/{ticket_id}/messages/{note_id}/attachments/0")).status_code == 200

    who.student()
    assert (await client.get(f"{API}/tickets/{ticket_id}/messages/{note_id}/attachments/0")).status_code == 404
    reply = await client.post(f"{API}/tickets/{ticket_id}/replies", json={"body": "Receipt attached", "attachments": [await _upload(client, s3_bucket, settings, "receipt.pdf")]})
    assert reply.status_code == 201 and reply.json()["reply"]["attachments"][0]["size_bytes"] > 0
