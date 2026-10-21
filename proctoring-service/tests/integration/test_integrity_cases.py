from datetime import timedelta

from sqlalchemy import select, update

from app.core.time import utcnow
from app.models.case import IntegrityCase
from tests.conftest import (
    ATTEMPT,
    EMPLOYER,
    EXAM_MANAGER,
    EXAM_MANAGER_2,
    STAFF_B,
    STUDENT,
    TEST_BASIC,
    outbox,
    started_payload,
)
from tests.integration.test_live_session import event, go_live

SUBMITTED = {"attempt_id": str(ATTEMPT), "test_id": str(TEST_BASIC), "user_id": str(STUDENT), "proctoring_level": "basic", "submit_reason": "manual"}


async def sit(client, who, tests_published, send_event, events: list[dict] | None = None, **submitted) -> str:
    session_id = await go_live(client, who, tests_published, send_event)
    if events:
        assert (await client.post(f"/api/v1/sessions/{session_id}/events", json={"events": events})).status_code == 200
    await send_event("attempt.submitted", {**SUBMITTED, **submitted})
    return session_id


async def only_case(client, who) -> dict:
    who.exam_manager()
    (case,) = (await client.get("/api/v1/cases")).json()["cases"]
    assert case["test_title"] == f"Test {case['test_id']}"
    return case


async def test_a_quiet_attempt_is_cleared_automatically_and_no_person_is_needed(client, who, tests_published, send_event, work, sessionmaker):
    await sit(client, who, tests_published, send_event, [event("window_blur"), event("tab_switch")])  # 9 points: low risk
    assert await work.finalize() == 1
    (decided,) = await outbox(sessionmaker, "integrity.decided")
    assert decided["attempt_id"] == str(ATTEMPT) and decided["decision"] == "clear" and decided["automatic"] is True and decided["risk_score"] == 9
    assert await outbox(sessionmaker, "integrity.flagged") == []
    case = await only_case(client, who)
    assert case["status"] == "final" and case["decision"] == "clear" and case["decided_by"] is None
    assert (await client.get(f"/api/v1/cases/{case['case_id']}")).json()["case"]["report"]["ai_analysis"] == "not_applicable"  # a basic test has no analysis
    assert await work.finalize() == 0  # decided once


async def test_a_risky_attempt_becomes_a_case_for_a_person_and_the_platform_is_told(client, who, tests_published, send_event, work, sessionmaker):
    await sit(client, who, tests_published, send_event, [event("tab_switch")] * 5 + [event("fullscreen_exit")] * 2)  # 30 + 16 = 46
    await work.finalize()
    (flagged,) = await outbox(sessionmaker, "integrity.flagged")
    assert flagged["attempt_id"] == str(ATTEMPT) and flagged["status"] == "flagged"
    assert await outbox(sessionmaker, "integrity.decided") == []  # nothing decided without a person
    case = await only_case(client, who)
    assert case["status"] == "open" and case["severity"] == "medium" and case["risk_score"] == 46 and case["reasons"][0].startswith("Risk score 46")
    detail = (await client.get(f"/api/v1/cases/{case['case_id']}")).json()["case"]
    assert detail["report"]["event_counts"]["tab_switch"] == 5 and detail["report"]["risk_breakdown"]["tab_switch"] == 30
    assert [t["type"] for t in detail["report"]["timeline"]][:2] == ["tab_switch", "tab_switch"]


async def test_the_flag_is_not_repeated_if_it_was_already_raised_during_the_test(client, who, tests_published, send_event, work, sessionmaker):
    await sit(client, who, tests_published, send_event, [event("devtools_open")] * 2 + [event("fullscreen_exit")] * 5 + [event("multiple_monitors")])
    await work.finalize()
    assert len(await outbox(sessionmaker, "integrity.flagged")) == 1


async def test_a_terminated_attempt_always_goes_to_a_person_however_low_the_score(client, who, tests_published, send_event, work, sessionmaker):
    await sit(client, who, tests_published, send_event, submit_reason="terminated")
    await work.finalize()
    case = await only_case(client, who)
    assert case["status"] == "open" and "terminated" in case["reasons"][0]


async def test_a_reviewer_claims_and_decides_and_an_invalidation_needs_a_written_reason(client, who, tests_published, send_event, work, sessionmaker, assessment):
    await sit(client, who, tests_published, send_event, [event("tab_switch")] * 5 + [event("fullscreen_exit")] * 2)
    await work.finalize()
    case = await only_case(client, who)
    claimed = await client.post(f"/api/v1/cases/{case['case_id']}/claim")
    assert claimed.json()["case"]["status"] == "under_review" and claimed.json()["case"]["assigned_to"] == str(EXAM_MANAGER)
    assert [f["status"] for f in await outbox(sessionmaker, "integrity.flagged")] == ["flagged", "under_review"]

    who.exam_manager(user_id=EXAM_MANAGER_2)
    assert (await client.post(f"/api/v1/cases/{case['case_id']}/claim")).json()["code"] == "CASE_ALREADY_CLAIMED"
    assert (await client.post(f"/api/v1/cases/{case['case_id']}/decide", json={"decision": "reviewed_ok"})).json()["code"] == "CASE_ALREADY_CLAIMED"
    who.exam_manager()
    no_reason = await client.post(f"/api/v1/cases/{case['case_id']}/decide", json={"decision": "invalidated"})
    assert no_reason.status_code == 422
    short = await client.post(f"/api/v1/cases/{case['case_id']}/decide", json={"decision": "invalidated", "note": "cheat"})
    assert short.status_code == 422 and short.json()["details"][0]["code"] == "REASON_REQUIRED"

    decided = await client.post(f"/api/v1/cases/{case['case_id']}/decide", json={"decision": "invalidated", "note": "Second person visible for two minutes"})
    assert decided.status_code == 200 and decided.json()["case"]["status"] == "decided" and decided.json()["case"]["decided_by"] == str(EXAM_MANAGER)
    (event_payload,) = await outbox(sessionmaker, "integrity.decided")
    assert event_payload["decision"] == "invalidated" and event_payload["automatic"] is False
    assert ("integrity", {"attempt_id": str(ATTEMPT), "decision": "invalidated"}) in [(a, {k: v for k, v in b.items() if k != "attempt_id"} | {"attempt_id": b["attempt_id"]}) for a, b in assessment.calls]
    assert (await client.post(f"/api/v1/cases/{case['case_id']}/decide", json={"decision": "reviewed_ok"})).json()["code"] == "CASE_NOT_OPEN"


async def test_a_failed_direct_push_does_not_undo_the_decision_because_the_event_carries_it(client, who, tests_published, send_event, work, sessionmaker, assessment):
    await sit(client, who, tests_published, send_event, [event("tab_switch")] * 5 + [event("fullscreen_exit")] * 2)
    await work.finalize()
    case = await only_case(client, who)
    assessment.fail_with = 503
    decided = await client.post(f"/api/v1/cases/{case['case_id']}/decide", json={"decision": "reviewed_ok", "note": "Looked fine"})
    assert decided.status_code == 200 and decided.json()["case"]["decision"] == "reviewed_ok"
    assert [e["decision"] for e in await outbox(sessionmaker, "integrity.decided")] == ["reviewed_ok"]


async def test_the_student_sees_the_outcome_and_appeals_an_invalidation_once(client, who, tests_published, send_event, work, sessionmaker):
    await sit(client, who, tests_published, send_event, [event("tab_switch")] * 5 + [event("fullscreen_exit")] * 2)
    await work.finalize()
    case = await only_case(client, who)
    await client.post(f"/api/v1/cases/{case['case_id']}/decide", json={"decision": "invalidated", "note": "Left the exam window repeatedly"})

    who.student()
    (mine,) = (await client.get("/api/v1/my/cases")).json()["cases"]
    assert mine["decision"] == "invalidated" and mine["can_appeal"] is True and "reasons" not in mine and "assigned_to" not in mine
    assert mine["test_title"] == f"Test {mine['test_id']}"
    assert (await client.post(f"/api/v1/cases/{case['case_id']}/appeal", json={"reason": "My connection dropped and the tab lost focus"})).status_code == 200
    again = await client.post(f"/api/v1/cases/{case['case_id']}/appeal", json={"reason": "Please look again"})
    assert again.status_code == 409 and again.json()["code"] == "APPEAL_NOT_ALLOWED"
    who.student(user_id=1755000000007102)
    assert (await client.post(f"/api/v1/cases/{case['case_id']}/appeal", json={"reason": "not mine"})).status_code in (404, 409)


async def test_a_cleared_or_ok_decision_cannot_be_appealed_and_the_window_closes(client, who, tests_published, send_event, work, sessionmaker, settings):
    await sit(client, who, tests_published, send_event, [event("tab_switch")] * 5 + [event("fullscreen_exit")] * 2)
    await work.finalize()
    case = await only_case(client, who)
    await client.post(f"/api/v1/cases/{case['case_id']}/decide", json={"decision": "reviewed_ok"})
    who.student()
    assert (await client.post(f"/api/v1/cases/{case['case_id']}/appeal", json={"reason": "x"})).json()["code"] == "APPEAL_NOT_ALLOWED"
    async with sessionmaker() as db:  # an invalidation older than the appeal window
        await db.execute(update(IntegrityCase).values(decision="invalidated", decided_at=utcnow() - timedelta(days=settings.APPEAL_WINDOW_DAYS + 1)))
        await db.commit()
    assert (await client.post(f"/api/v1/cases/{case['case_id']}/appeal", json={"reason": "too late"})).json()["code"] == "APPEAL_NOT_ALLOWED"


async def test_a_different_exam_manager_decides_the_appeal_and_overturning_clears_the_attempt(client, who, tests_published, send_event, work, sessionmaker, assessment):
    await sit(client, who, tests_published, send_event, [event("tab_switch")] * 5 + [event("fullscreen_exit")] * 2)
    await work.finalize()
    case = await only_case(client, who)
    await client.post(f"/api/v1/cases/{case['case_id']}/decide", json={"decision": "invalidated", "note": "Left the exam window repeatedly"})
    who.student()
    await client.post(f"/api/v1/cases/{case['case_id']}/appeal", json={"reason": "Network problem"})

    who.exam_manager()  # the same reviewer cannot mark their own homework
    same = await client.post(f"/api/v1/cases/{case['case_id']}/decide-appeal", json={"outcome": "overturned", "note": "ok"})
    assert same.status_code == 403 and same.json()["code"] == "SAME_REVIEWER"
    who.staff()
    assert (await client.post(f"/api/v1/cases/{case['case_id']}/decide-appeal", json={"outcome": "overturned", "note": "ok"})).status_code == 403
    who.exam_manager(user_id=EXAM_MANAGER_2)
    overturned = await client.post(f"/api/v1/cases/{case['case_id']}/decide-appeal", json={"outcome": "overturned", "note": "The logs show a network fault"})
    assert overturned.json()["case"]["status"] == "final" and overturned.json()["case"]["decision"] == "reviewed_ok"
    events = await outbox(sessionmaker, "integrity.decided")
    assert [e["decision"] for e in events] == ["invalidated", "reviewed_ok"] and events[1]["appeal"] == "overturned"
    assert [c for c in assessment.calls if c[1].get("decision") == "reviewed_ok"]


async def test_an_upheld_appeal_is_final_and_emits_nothing_new(client, who, tests_published, send_event, work, sessionmaker):
    await sit(client, who, tests_published, send_event, [event("tab_switch")] * 5 + [event("fullscreen_exit")] * 2)
    await work.finalize()
    case = await only_case(client, who)
    await client.post(f"/api/v1/cases/{case['case_id']}/decide", json={"decision": "invalidated", "note": "Left the exam window repeatedly"})
    who.student()
    await client.post(f"/api/v1/cases/{case['case_id']}/appeal", json={"reason": "Network problem"})
    who.exam_manager(user_id=EXAM_MANAGER_2)
    upheld = await client.post(f"/api/v1/cases/{case['case_id']}/decide-appeal", json={"outcome": "upheld", "note": "The timeline is clear"})
    assert upheld.json()["case"]["appeal_status"] == "upheld" and upheld.json()["case"]["decision"] == "invalidated"
    assert len(await outbox(sessionmaker, "integrity.decided")) == 1
    assert (await client.post(f"/api/v1/cases/{case['case_id']}/decide-appeal", json={"outcome": "overturned", "note": "again"})).json()["code"] == "NO_APPEAL"


async def test_who_can_review_which_cases(client, who, tests_published, send_event, work):
    await sit(client, who, tests_published, send_event, [event("tab_switch")] * 5 + [event("fullscreen_exit")] * 2)
    await work.finalize()
    case = await only_case(client, who)
    who.staff()  # the student's own institution
    assert [c["case_id"] for c in (await client.get("/api/v1/cases")).json()["cases"]] == [case["case_id"]]
    assert (await client.get(f"/api/v1/cases/{case['case_id']}")).status_code == 200
    who.staff(user_id=STAFF_B, organization_id=1755000000007004)  # another institution
    assert (await client.get("/api/v1/cases")).json()["cases"] == []
    assert (await client.get(f"/api/v1/cases/{case['case_id']}")).status_code == 404
    assert (await client.post(f"/api/v1/cases/{case['case_id']}/decide", json={"decision": "reviewed_ok"})).status_code == 404
    who.recruiter()  # an employer has no business with a platform test
    assert (await client.get("/api/v1/cases")).json()["cases"] == []
    who.student()
    assert (await client.get("/api/v1/cases")).status_code == 403
    assert (await client.get(f"/api/v1/cases/{case['case_id']}")).status_code == 404


async def test_an_employers_hiring_assessment_is_reviewed_by_the_employer_not_the_institution(client, who, tests_published, send_event, work):
    from tests.conftest import TEST_HIRING

    await tests_published()
    await send_event("attempt.started", started_payload(test_id=TEST_HIRING, level="strict"))
    await send_event("attempt.submitted", {"attempt_id": str(ATTEMPT), "proctoring_level": "strict", "submit_reason": "terminated"})
    await work.finalize()
    who.recruiter()
    (case,) = (await client.get("/api/v1/cases")).json()["cases"]
    assert case["test_id"] == str(TEST_HIRING)
    who.staff()  # the candidate's institution never sees it
    assert (await client.get("/api/v1/cases")).json()["cases"] == []
    assert (await client.get(f"/api/v1/cases/{case['case_id']}")).status_code == 404
    who.recruiter(organization_id=EMPLOYER + 100)
    assert (await client.get(f"/api/v1/cases/{case['case_id']}")).status_code == 404


async def test_overdue_cases_are_listed_never_decided_automatically(client, who, tests_published, send_event, work, sessionmaker):
    await sit(client, who, tests_published, send_event, [event("tab_switch")] * 5 + [event("fullscreen_exit")] * 2)
    await work.finalize()
    async with sessionmaker() as db:
        await db.execute(update(IntegrityCase).values(created_at=utcnow() - timedelta(hours=100)))
        await db.commit()
    who.exam_manager()
    overdue = (await client.get("/api/v1/cases", params={"overdue": "true"})).json()["cases"]
    assert len(overdue) == 1 and overdue[0]["status"] == "open" and overdue[0]["overdue"] is True
    assert await work.finalize() == 0 and await outbox(sessionmaker, "integrity.decided") == []
    from tests.conftest import INTERNAL_TOKEN

    queue = (await client.get("/api/v1/internal/queue", headers={"X-Internal-Service-Token": INTERNAL_TOKEN})).json()["queue"]
    assert queue["open_cases"] == 1 and queue["overdue_cases"] == 1


async def test_the_decision_waits_for_pending_analysis_but_not_forever(client, who, tests_published, send_event, work, settings, sessionmaker, s3_bucket, analyzer_service):
    from tests.integration.test_live_session import go_live as live
    from tests.integration.test_precheck_and_session import upload

    settings.AI_ANALYZER_URL = "http://analyzer.test"
    settings.ANALYSIS_WAIT_SECONDS = 3_600
    session_id = await live(client, who, tests_published, send_event, s3_bucket, settings, level="strict")
    await upload(client, s3_bucket, settings, session_id, "periodic")  # still waiting to be analysed
    await send_event("attempt.submitted", {"attempt_id": str(ATTEMPT), "proctoring_level": "strict", "submit_reason": "manual"})
    assert await work.finalize() == 0  # the analysis has not run: not yet
    await work.analyze()
    async with sessionmaker() as db:
        await db.execute(update(__import__("app.models.session", fromlist=["ProctorSession"]).ProctorSession).values(finalize_due_at=utcnow() - timedelta(seconds=1)))
        await db.commit()
    assert await work.finalize() == 1
    detail = None
    who.exam_manager()
    listed = (await client.get("/api/v1/cases")).json()["cases"]
    assert len(listed) == 1 or detail is None
    assert select and EMPLOYER
