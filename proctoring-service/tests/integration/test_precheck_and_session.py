import boto3
from sqlalchemy import select

from app.models.session import ProctorEvent, ProctorSession
from tests.conftest import ATTEMPT, EMPLOYER, STUDENT, TEST_BASIC, TEST_STRICT, outbox, started_payload

GOOD = {"consent": True, "consent_version": "2026-09", "browser": "Chrome 129", "fullscreen_supported": True, "camera": True, "microphone": True, "bandwidth_kbps": 900}


async def create(client, who, tests_published, test_id=TEST_BASIC) -> dict:
    await tests_published()
    who.student()
    response = await client.post("/api/v1/sessions", json={"test_id": str(test_id)})
    assert response.status_code == 201, response.text
    return response.json()


async def upload(client, s3_bucket, settings, session_id: str, kind: str) -> dict:
    issued = await client.post(f"/api/v1/sessions/{session_id}/snapshots/upload-url", json={"kind": kind})
    assert issued.status_code == 200, issued.text
    key = issued.json()["file"]["key"]
    s3_bucket.put_object(Bucket=settings.S3_BUCKET, Key=key, Body=b"\xff\xd8\xff fake jpeg", ContentType="image/jpeg")
    registered = await client.post(f"/api/v1/sessions/{session_id}/snapshots", json={"kind": kind, "key": key})
    assert registered.status_code == 201, registered.text
    return registered.json()["snapshot"]


async def test_a_proctored_test_starts_a_precheck_with_its_requirements(client, who, tests_published):
    body = await create(client, who, tests_published, TEST_STRICT)
    assert body["session"]["status"] == "precheck" and body["session"]["level"] == "strict"
    assert body["requirements"]["needs"] == ["consent", "fullscreen", "camera", "microphone", "bandwidth", "id_photo", "face_enrolment"]
    assert body["requirements"]["snapshot_interval_seconds"] == 25 and body["requirements"]["consent_version"] == "2026-09"
    basic = await create(client, who, tests_published, TEST_BASIC)
    assert basic["requirements"]["needs"] == ["consent", "fullscreen"]


async def test_only_proctored_tests_have_a_precheck_and_only_students_take_it(client, who, tests_published):
    await tests_published()
    who.student()
    assert (await client.post("/api/v1/sessions", json={"test_id": "1755000000000599"})).json()["code"] == "TEST_NOT_PROCTORED"  # proctoring: none
    assert (await client.post("/api/v1/sessions", json={"test_id": "1755000000001234"})).status_code == 404  # unknown
    who.staff()
    assert (await client.post("/api/v1/sessions", json={"test_id": str(TEST_BASIC)})).status_code == 403


async def test_a_second_tab_gets_the_same_session(client, who, tests_published):
    first = await create(client, who, tests_published)
    second = await client.post("/api/v1/sessions", json={"test_id": str(TEST_BASIC)})
    assert second.json()["session"]["session_id"] == first["session"]["session_id"]


async def test_a_basic_precheck_needs_consent_and_fullscreen_and_publishes_the_ready_flag(client, who, tests_published, redis):
    session_id = (await create(client, who, tests_published))["session"]["session_id"]
    bad = await client.post(f"/api/v1/sessions/{session_id}/precheck", json={**GOOD, "consent": False, "fullscreen_supported": False})
    assert bad.status_code == 200 and bad.json()["ready"] is False
    assert {f["code"] for f in bad.json()["failures"]} == {"CONSENT_REQUIRED", "FULLSCREEN_UNSUPPORTED"}
    assert await redis.exists(f"lms:proctor:ready:{STUDENT}:{TEST_BASIC}") == 0  # assessment-service would refuse to start

    stale = await client.post(f"/api/v1/sessions/{session_id}/precheck", json={**GOOD, "consent_version": "2019-01"})
    assert stale.json()["failures"][0]["code"] == "CONSENT_REQUIRED"  # consent to an old text does not count

    ok = await client.post(f"/api/v1/sessions/{session_id}/precheck", json=GOOD)
    assert ok.json()["ready"] is True and ok.json()["session"]["status"] == "ready"
    assert await redis.exists(f"lms:proctor:ready:{STUDENT}:{TEST_BASIC}") == 1
    assert 0 < await redis.ttl(f"lms:proctor:ready:{STUDENT}:{TEST_BASIC}") <= 7200


async def test_a_strict_precheck_also_needs_devices_bandwidth_and_identity_photos(client, who, tests_published, s3_bucket, settings, redis):
    session_id = (await create(client, who, tests_published, TEST_STRICT))["session"]["session_id"]
    weak = await client.post(f"/api/v1/sessions/{session_id}/precheck", json={**GOOD, "camera": False, "microphone": False, "bandwidth_kbps": 50})
    assert {f["code"] for f in weak.json()["failures"]} == {"CAMERA_REQUIRED", "MICROPHONE_REQUIRED", "BANDWIDTH_TOO_LOW", "ID_PHOTO_REQUIRED", "FACE_ENROLMENT_REQUIRED"}

    await upload(client, s3_bucket, settings, session_id, "id_photo")
    partial = await client.post(f"/api/v1/sessions/{session_id}/precheck", json=GOOD)
    assert [f["code"] for f in partial.json()["failures"]] == ["FACE_ENROLMENT_REQUIRED"]
    await upload(client, s3_bucket, settings, session_id, "face_enrol")
    ready = await client.post(f"/api/v1/sessions/{session_id}/precheck", json=GOOD)
    assert ready.json()["ready"] is True
    assert await redis.exists(f"lms:proctor:ready:{STUDENT}:{TEST_STRICT}") == 1


async def test_basic_proctoring_takes_no_snapshots_and_a_strict_client_cannot_register_someone_elses_file(client, who, tests_published, s3_bucket, settings):
    basic = (await create(client, who, tests_published))["session"]["session_id"]
    refused = await client.post(f"/api/v1/sessions/{basic}/snapshots/upload-url", json={"kind": "id_photo"})
    assert refused.status_code == 409 and refused.json()["code"] == "NOT_APPLICABLE"

    strict = (await create(client, who, tests_published, TEST_STRICT))["session"]["session_id"]
    s3_bucket.put_object(Bucket=settings.S3_BUCKET, Key="sessions/999/id_photo/x.jpg", Body=b"x")
    stolen = await client.post(f"/api/v1/sessions/{strict}/snapshots", json={"kind": "id_photo", "key": "sessions/999/id_photo/x.jpg"})
    assert stolen.status_code == 422 and stolen.json()["details"][0]["code"] == "INVALID_KEY"
    missing = await client.post(f"/api/v1/sessions/{strict}/snapshots", json={"kind": "id_photo", "key": f"sessions/{strict}/id_photo/never.jpg"})
    assert missing.json()["details"][0]["code"] == "FILE_NOT_UPLOADED"
    periodic = await client.post(f"/api/v1/sessions/{strict}/snapshots/upload-url", json={"kind": "periodic"})
    assert periodic.status_code == 409 and periodic.json()["code"] == "SESSION_NOT_ACTIVE"  # only while the test runs
    mismatched = await client.post(f"/api/v1/sessions/{strict}/snapshots/upload-url", json={"kind": "id_photo", "content_type": "audio/webm"})
    assert mismatched.status_code == 422 and mismatched.json()["details"][0]["code"] == "INVALID_TYPE"  # audio only for audio clips


async def test_starting_the_attempt_links_the_session_makes_it_active_and_consumes_the_ready_flag(client, who, tests_published, send_event, redis, sessionmaker):
    session_id = (await create(client, who, tests_published))["session"]["session_id"]
    await client.post(f"/api/v1/sessions/{session_id}/precheck", json=GOOD)
    await send_event("attempt.started", started_payload())
    who.student()
    session = (await client.get(f"/api/v1/sessions/{session_id}")).json()["session"]
    assert session["status"] == "active" and session["attempt_id"] == str(ATTEMPT) and session["started_at"]
    assert await redis.exists(f"lms:proctor:ready:{STUDENT}:{TEST_BASIC}") == 0
    async with sessionmaker() as db:
        assert (await db.execute(select(ProctorEvent.event_type).where(ProctorEvent.event_type == "precheck_missing"))).first() is None


async def test_starting_without_a_precheck_still_creates_a_session_and_scores_the_gap(client, who, tests_published, send_event, sessionmaker):
    await tests_published()
    await send_event("attempt.started", started_payload())
    await send_event("attempt.started", started_payload(), event_id="another-delivery")  # a redelivery links nothing new
    async with sessionmaker() as db:
        (session,) = (await db.execute(select(ProctorSession))).scalars().all()
        assert session.status == "active" and session.risk_breakdown == {"precheck_missing": 15} and session.risk_score == 15


async def test_unproctored_attempts_are_ignored(send_event, sessionmaker, tests_published):
    await tests_published()
    await send_event("attempt.started", started_payload(level="none"))
    async with sessionmaker() as db:
        assert (await db.execute(select(ProctorSession))).scalars().all() == []


async def test_a_new_attempt_supersedes_an_older_open_session_and_flags_two_live_ones(client, who, tests_published, send_event, sessionmaker):
    await tests_published()
    who.student()
    first = (await client.post("/api/v1/sessions", json={"test_id": str(TEST_BASIC)})).json()["session"]["session_id"]
    await send_event("attempt.started", started_payload(attempt=ATTEMPT))  # the first attempt goes live on the first session
    async with sessionmaker() as db:  # ... and a second pre-check was opened on another device
        db.add(ProctorSession(public_id=1755000000000001, test_id=TEST_BASIC, user_id=STUDENT, organization_id=1755000000007003, level="basic", risk_breakdown={}, status="active"))
        await db.commit()
    await send_event("attempt.started", started_payload(attempt=ATTEMPT + 1))
    async with sessionmaker() as db:
        rows = {s.attempt_id: s for s in (await db.execute(select(ProctorSession))).scalars()}
        statuses = sorted(s.status for s in (await db.execute(select(ProctorSession))).scalars())
    assert statuses.count("superseded") >= 1 and rows[ATTEMPT + 1].status == "active"
    assert "multiple_sessions" in rows[ATTEMPT + 1].risk_breakdown
    assert first and EMPLOYER and boto3 and await outbox(sessionmaker, "integrity.flagged") == []
