from datetime import timedelta

from sqlalchemy import select, update

from app.core.time import utcnow
from app.models.session import ProctorEvent, ProctorSession, Snapshot
from tests.conftest import ATTEMPT, STUDENT, TEST_BASIC, TEST_STRICT, outbox, started_payload
from tests.integration.test_precheck_and_session import GOOD, upload


async def go_live(client, who, tests_published, send_event, s3_bucket=None, settings=None, *, level="basic") -> str:
    """A properly pre-checked student whose attempt has started; returns the session id."""
    await tests_published()
    who.student()
    test_id = TEST_BASIC if level == "basic" else TEST_STRICT
    session_id = (await client.post("/api/v1/sessions", json={"test_id": str(test_id)})).json()["session"]["session_id"]
    if level == "strict":
        await upload(client, s3_bucket, settings, session_id, "id_photo")
        await upload(client, s3_bucket, settings, session_id, "face_enrol")
    assert (await client.post(f"/api/v1/sessions/{session_id}/precheck", json=GOOD)).json()["ready"] is True
    await send_event("attempt.started", started_payload(test_id=test_id, level=level))
    who.student()
    return session_id


def event(kind: str, **fields) -> dict:
    return {"type": kind, **fields}


async def test_browser_events_add_weighted_risk_capped_per_type(client, who, tests_published, send_event):
    session_id = await go_live(client, who, tests_published, send_event)
    body = (await client.post(f"/api/v1/sessions/{session_id}/events", json={"events": [event("tab_switch")] * 3 + [event("fullscreen_exit"), event("copy_paste")]})).json()
    assert body["accepted"] == 5 and body["rejected"] == [] and body["risk_score"] == 3 * 6 + 8 + 5
    flood = (await client.post(f"/api/v1/sessions/{session_id}/events", json={"events": [event("tab_switch")] * 50})).json()
    assert flood["accepted"] == 50 and flood["risk_score"] == 30 + 8 + 5  # fifty tab switches cost no more than the type's 30-point cap


async def test_a_client_cannot_report_ai_findings_or_staff_actions_or_camera_events_in_a_basic_session(client, who, tests_published, send_event):
    session_id = await go_live(client, who, tests_published, send_event)
    body = (await client.post(f"/api/v1/sessions/{session_id}/events", json={"events": [event("multiple_faces"), event("terminated"), event("camera_off"), event("invented"), event("window_blur")]})).json()
    assert body["accepted"] == 1 and {r["type"] for r in body["rejected"]} == {"multiple_faces", "terminated", "camera_off", "invented"}
    assert body["risk_score"] == 3


async def test_events_are_only_taken_while_the_test_runs_and_only_from_the_owner(client, who, tests_published, send_event):
    await tests_published()
    who.student()
    session_id = (await client.post("/api/v1/sessions", json={"test_id": str(TEST_BASIC)})).json()["session"]["session_id"]
    assert (await client.post(f"/api/v1/sessions/{session_id}/events", json={"events": [event("tab_switch")]})).json()["code"] == "SESSION_NOT_ACTIVE"
    await client.post(f"/api/v1/sessions/{session_id}/precheck", json=GOOD)
    await send_event("attempt.started", started_payload())
    who.student(user_id=1755000000007102)
    assert (await client.post(f"/api/v1/sessions/{session_id}/events", json={"events": [event("tab_switch")]})).status_code == 404
    assert (await client.get(f"/api/v1/sessions/{session_id}")).status_code == 404


async def test_a_client_clock_cannot_backdate_the_timeline(client, who, tests_published, send_event, sessionmaker):
    session_id = await go_live(client, who, tests_published, send_event)
    long_ago = (utcnow() - timedelta(days=3)).isoformat()
    await client.post(f"/api/v1/sessions/{session_id}/events", json={"events": [event("tab_switch", occurred_at=long_ago), event("window_blur", occurred_at="2026-09-21T10:00:00")]})
    async with sessionmaker() as db:
        stamps = [e.occurred_at for e in (await db.execute(select(ProctorEvent).where(ProctorEvent.event_type.in_(["tab_switch", "window_blur"])))).scalars()]
    assert all(abs((s - utcnow()).total_seconds()) < 5 for s in stamps)  # both were stamped by the server


async def test_crossing_the_live_threshold_flags_the_attempt_once(client, who, tests_published, send_event, sessionmaker):
    session_id = await go_live(client, who, tests_published, send_event)
    await client.post(f"/api/v1/sessions/{session_id}/events", json={"events": [event("devtools_open")] * 2 + [event("fullscreen_exit")] * 5})  # 30 + 40
    await client.post(f"/api/v1/sessions/{session_id}/events", json={"events": [event("multiple_monitors")]})
    (flagged,) = await outbox(sessionmaker, "integrity.flagged")  # once, not on every event past the threshold
    assert flagged["attempt_id"] == str(ATTEMPT) and flagged["status"] == "flagged" and flagged["risk_score"] >= 50
    who.exam_manager()
    listed = (await client.get("/api/v1/monitor/sessions", params={"min_risk": 50})).json()["sessions"]
    assert [s["session_id"] for s in listed] == [session_id]


async def test_a_heartbeat_returns_staff_warnings_exactly_once_and_notices_a_new_ip_or_device(client, who, tests_published, send_event, sessionmaker):
    session_id = await go_live(client, who, tests_published, send_event)
    first = (await client.post(f"/api/v1/sessions/{session_id}/heartbeat", json={"device_fingerprint": "device-1"})).json()
    assert first["session_status"] == "active" and first["directives"] == [] and first["snapshot_interval_seconds"] == 25

    who.exam_manager()
    assert (await client.post(f"/api/v1/monitor/sessions/{session_id}/warn", json={"message": "Keep your eyes on the screen"})).status_code == 200
    who.student()
    beat = (await client.post(f"/api/v1/sessions/{session_id}/heartbeat", json={})).json()
    assert [(d["kind"], d["message"]) for d in beat["directives"]] == [("warn", "Keep your eyes on the screen")]
    assert (await client.post(f"/api/v1/sessions/{session_id}/heartbeat", json={})).json()["directives"] == []  # delivered once

    async with sessionmaker() as db:
        await db.execute(update(ProctorSession).values(device_fingerprint="device-1", ip_address="10.9.9.9"))
        await db.commit()
    await client.post(f"/api/v1/sessions/{session_id}/heartbeat", json={"device_fingerprint": "device-2"})
    async with sessionmaker() as db:
        breakdown = (await db.execute(select(ProctorSession.risk_breakdown))).scalar_one()
    assert breakdown["ip_changed"] == 5 and breakdown["device_changed"] == 15


async def test_a_client_that_goes_quiet_is_scored_once_per_gap(client, who, tests_published, send_event, work, sessionmaker):
    session_id = await go_live(client, who, tests_published, send_event)
    await client.post(f"/api/v1/sessions/{session_id}/heartbeat", json={})
    assert await work.heartbeats() == 0  # it just spoke
    async with sessionmaker() as db:
        await db.execute(update(ProctorSession).values(last_heartbeat_at=utcnow() - timedelta(minutes=5)))
        await db.commit()
    assert await work.heartbeats() == 1 and await work.heartbeats() == 0  # the gap is scored once, not every sweep
    async with sessionmaker() as db:
        assert (await db.execute(select(ProctorSession.risk_breakdown))).scalar_one()["heartbeat_lost"] == 6
    await client.post(f"/api/v1/sessions/{session_id}/heartbeat", json={})  # back
    async with sessionmaker() as db:
        await db.execute(update(ProctorSession).values(last_heartbeat_at=utcnow() - timedelta(minutes=5)))
        await db.commit()
    assert await work.heartbeats() == 1  # a new gap counts again


async def test_periodic_snapshots_are_taken_only_in_strict_sessions_and_get_sequence_numbers(client, who, tests_published, send_event, s3_bucket, settings):
    session_id = await go_live(client, who, tests_published, send_event, s3_bucket, settings, level="strict")
    first = await upload(client, s3_bucket, settings, session_id, "periodic")
    second = await upload(client, s3_bucket, settings, session_id, "periodic")
    assert (first["sequence"], second["sequence"]) == (1, 2)
    assert first["analysis_status"] == "skipped"  # no analyzer is configured: stored, and honestly marked


async def test_strict_media_events_are_accepted_from_strict_clients(client, who, tests_published, send_event, s3_bucket, settings):
    session_id = await go_live(client, who, tests_published, send_event, s3_bucket, settings, level="strict")
    body = (await client.post(f"/api/v1/sessions/{session_id}/events", json={"events": [event("camera_off"), event("mic_off"), event("screen_share_stopped")]})).json()
    assert body["accepted"] == 3 and body["risk_score"] == 10 + 4 + 10


async def test_the_endpoints_are_rate_limited_per_session(client, who, tests_published, send_event, settings):
    settings.RATE_LIMIT_ENABLED = True
    settings.EVENTS_RATE_LIMIT_PER_SESSION_PER_MINUTE = 2
    session_id = await go_live(client, who, tests_published, send_event)
    codes = [(await client.post(f"/api/v1/sessions/{session_id}/events", json={"events": [event("window_blur")]})).status_code for _ in range(4)]
    assert codes == [200, 200, 429, 429]
    assert STUDENT and Snapshot
