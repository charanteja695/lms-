from sqlalchemy import select

from app.models.session import MediaAccess, ProctorEvent, ProctorSession
from tests.conftest import ATTEMPT, EMPLOYER, EXAM_MANAGER, ORG_A, STAFF_A, STAFF_B, STUDENT, TEST_BASIC, outbox
from tests.integration.test_live_session import event, go_live
from tests.integration.test_precheck_and_session import upload

SUBMITTED = {"attempt_id": str(ATTEMPT), "test_id": str(TEST_BASIC), "proctoring_level": "basic", "submit_reason": "manual"}


async def test_staff_see_running_sessions_scoped_to_their_own_students(client, who, tests_published, send_event):
    session_id = await go_live(client, who, tests_published, send_event)
    await client.post(f"/api/v1/sessions/{session_id}/events", json={"events": [event("tab_switch")]})
    who.staff()
    assert [s["session_id"] for s in (await client.get("/api/v1/monitor/sessions")).json()["sessions"]] == [session_id]
    detail = (await client.get(f"/api/v1/monitor/sessions/{session_id}")).json()
    assert detail["session"]["risk_score"] == 6 and detail["session"]["risk_breakdown"] == {"tab_switch": 6}
    assert [e["type"] for e in detail["events"]][:2] == ["tab_switch", "session_started"]
    who.staff(user_id=STAFF_B, organization_id=1755000000007004)
    assert (await client.get("/api/v1/monitor/sessions")).json()["sessions"] == []
    assert (await client.get(f"/api/v1/monitor/sessions/{session_id}")).status_code == 404
    assert (await client.post(f"/api/v1/monitor/sessions/{session_id}/warn", json={"message": "hello"})).status_code == 404
    who.student()
    assert (await client.get("/api/v1/monitor/sessions")).status_code == 403


async def test_pause_resume_and_terminate_act_on_the_attempt_and_are_recorded(client, who, tests_published, send_event, assessment, sessionmaker):
    session_id = await go_live(client, who, tests_published, send_event)
    who.exam_manager()
    assert (await client.post(f"/api/v1/monitor/sessions/{session_id}/pause", json={"message": "Noise in the room"})).status_code == 200
    assert (await client.post(f"/api/v1/monitor/sessions/{session_id}/resume")).status_code == 200
    terminated = await client.post(f"/api/v1/monitor/sessions/{session_id}/terminate", json={"message": "Second person"})
    assert terminated.status_code == 200 and terminated.json()["session"]["terminated"] is True and terminated.json()["session"]["critical"] is True
    assert [(a, b["attempt_id"]) for a, b in assessment.calls] == [("pause", str(ATTEMPT)), ("unpause", str(ATTEMPT)), ("terminate", str(ATTEMPT))]
    assert assessment.calls[0][1]["reason"] == "Noise in the room"
    assert [d["kind"] for d in terminated.json()["directives"]] == ["terminate", "resume", "pause"]
    (flagged,) = await outbox(sessionmaker, "integrity.flagged")  # terminating is critical: it flags, and a person will decide
    assert flagged["status"] == "flagged"


async def test_a_control_that_assessment_service_cannot_carry_out_changes_nothing(client, who, tests_published, send_event, assessment, sessionmaker):
    session_id = await go_live(client, who, tests_published, send_event)
    who.exam_manager()
    assessment.fail_with = 503
    down = await client.post(f"/api/v1/monitor/sessions/{session_id}/terminate", json={"message": "x"})
    assert down.status_code == 502 and down.json()["code"] == "ASSESSMENT_UNAVAILABLE"
    assessment.fail_with = 409
    refused = await client.post(f"/api/v1/monitor/sessions/{session_id}/pause", json={})
    assert refused.status_code == 409 and refused.json()["code"] == "ATTEMPT_NOT_CONTROLLABLE"
    async with sessionmaker() as db:
        session = (await db.execute(select(ProctorSession))).scalar_one()
        assert session.terminated is False and session.critical is False
        assert (await db.execute(select(ProctorEvent.event_type).where(ProctorEvent.event_type.in_(["terminated", "paused"])))).first() is None


async def test_only_a_running_test_can_be_controlled(client, who, tests_published, send_event):
    session_id = await go_live(client, who, tests_published, send_event)
    await send_event("attempt.submitted", SUBMITTED)
    who.exam_manager()
    assert (await client.post(f"/api/v1/monitor/sessions/{session_id}/pause", json={})).json()["code"] == "SESSION_NOT_ACTIVE"
    assert (await client.post(f"/api/v1/monitor/sessions/{session_id}/warn", json={"message": "too late"})).status_code == 409


async def test_an_employer_monitors_its_own_hiring_assessment_only(client, who, tests_published, send_event):
    from tests.conftest import TEST_HIRING, started_payload

    await tests_published()
    await send_event("attempt.started", started_payload(test_id=TEST_HIRING, level="strict"))
    who.recruiter()
    (listed,) = (await client.get("/api/v1/monitor/sessions")).json()["sessions"]
    who.recruiter(organization_id=EMPLOYER + 100)
    assert (await client.get(f"/api/v1/monitor/sessions/{listed['session_id']}")).status_code == 404
    who.staff()  # the candidate's institution has no view of an employer's assessment
    assert (await client.get("/api/v1/monitor/sessions")).json()["sessions"] == []


async def _risky_case(client, who, tests_published, send_event, work, s3_bucket, settings):
    session_id = await go_live(client, who, tests_published, send_event, s3_bucket, settings, level="strict")
    snapshot = await upload(client, s3_bucket, settings, session_id, "periodic")
    await client.post(f"/api/v1/sessions/{session_id}/events", json={"events": [event("tab_switch")] * 5 + [event("fullscreen_exit")] * 2})
    await send_event("attempt.submitted", {**SUBMITTED, "proctoring_level": "strict"})
    await work.finalize()
    who.exam_manager()
    (case,) = (await client.get("/api/v1/cases")).json()["cases"]
    return case, snapshot


async def test_every_view_of_a_snapshot_is_logged_and_the_report_says_when_nothing_was_analysed(client, who, tests_published, send_event, work, s3_bucket, settings, sessionmaker):
    case, snapshot = await _risky_case(client, who, tests_published, send_event, work, s3_bucket, settings)
    detail = (await client.get(f"/api/v1/cases/{case['case_id']}")).json()["case"]
    assert detail["report"]["ai_analysis"] == "unavailable"  # no analyzer: never "looked and found nothing"
    assert detail["report"]["snapshots"]["skipped"] == 7  # identity photos, four face-movement frames, one periodic
    assert {s["kind"] for s in detail["snapshots"]} == {"id_photo", "face_enrol", "liveness", "periodic"}

    link = await client.get(f"/api/v1/cases/{case['case_id']}/snapshots/{snapshot['snapshot_id']}/url")
    assert link.status_code == 200 and link.json()["url"].startswith("http") and link.json()["expires_in"] == 120
    async with sessionmaker() as db:
        (access,) = (await db.execute(select(MediaAccess))).scalars().all()
        assert access.viewer_user_id == EXAM_MANAGER and access.reason == "case_review"
    audit = (await client.get("/api/v1/audit/media-access")).json()["accesses"]
    assert [(a["snapshot_id"], a["viewer_user_id"]) for a in audit] == [(snapshot["snapshot_id"], str(EXAM_MANAGER))]
    who.staff()
    assert (await client.get("/api/v1/audit/media-access")).status_code == 403  # only exam managers read the audit log


async def test_media_of_another_case_or_another_owner_cannot_be_fetched(client, who, tests_published, send_event, work, s3_bucket, settings):
    case, snapshot = await _risky_case(client, who, tests_published, send_event, work, s3_bucket, settings)
    assert (await client.get(f"/api/v1/cases/{case['case_id']}/snapshots/1755000000001111/url")).status_code == 404
    who.staff(user_id=STAFF_B, organization_id=1755000000007004)
    assert (await client.get(f"/api/v1/cases/{case['case_id']}/snapshots/{snapshot['snapshot_id']}/url")).status_code == 404
    who.student()
    assert (await client.get(f"/api/v1/cases/{case['case_id']}/snapshots/{snapshot['snapshot_id']}/url")).status_code == 404
    assert STUDENT


async def test_a_purged_snapshot_can_no_longer_be_fetched(client, who, tests_published, send_event, work, s3_bucket, settings, sessionmaker):
    from datetime import timedelta

    from sqlalchemy import update

    from app.core.time import utcnow
    from app.models.session import Snapshot

    case, snapshot = await _risky_case(client, who, tests_published, send_event, work, s3_bucket, settings)
    async with sessionmaker() as db:
        await db.execute(update(Snapshot).values(delete_after=utcnow() - timedelta(seconds=1)))
        await db.commit()
    await work.housekeeping()
    gone = await client.get(f"/api/v1/cases/{case['case_id']}/snapshots/{snapshot['snapshot_id']}/url")
    assert gone.status_code == 404 and gone.json()["code"] == "MEDIA_DELETED"
    assert (await client.get(f"/api/v1/cases/{case['case_id']}")).status_code == 200  # the case and its timeline outlive the media


async def test_monitoring_follows_the_persons_permission(client, act_as):
    """A super admin can take live monitoring away from one staff member."""
    act_as(STAFF_A, role="staff", organization_id=ORG_A, defaults=False)
    assert (await client.get("/api/v1/monitor/sessions")).status_code == 403
    act_as(STAFF_A, role="staff", organization_id=ORG_A)
    assert (await client.get("/api/v1/monitor/sessions")).status_code == 200
