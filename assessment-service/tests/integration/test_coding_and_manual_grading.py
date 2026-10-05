from datetime import timedelta

import boto3
import pytest
from moto import mock_aws
from sqlalchemy import select, update

from app.core.time import utcnow
from app.models.attempt import Attempt, AttemptAnswer, CodingSubmission
from app.models.outbox_event import OutboxEvent
from tests.conftest import MODULE, coding, fixed, mcq, subjective, true_false

SOLUTION = {"language": "python", "source": "print(sum(map(int, input().split())))"}


async def outbox(sessionmaker, event_type: str) -> list[dict]:
    async with sessionmaker() as db:
        rows = (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == event_type).order_by(OutboxEvent.created_at))).scalars()
        return [row.payload for row in rows]


async def code_test(make_question, make_test, **fields):
    q_code = await make_question(coding(), default_marks=10)
    q_mcq = await make_question(mcq(correct="b"), default_marks=2)
    test_id = await make_test([fixed(q_code, 10), fixed(q_mcq, 2)], kind="module", target_id=str(MODULE), **fields)
    return test_id, q_code, q_mcq


async def submit_code(client, who, test_id, q_code, q_mcq, *, source=SOLUTION):
    who.student()
    attempt_id = (await client.post(f"/api/v1/tests/{test_id}/attempts", json={"start_now": True})).json()["attempt"]["attempt_id"]
    assert (await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_code}", json={"response": source, "revision": 1})).status_code == 200
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_mcq}", json={"response": {"selected": "b"}, "revision": 1})
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    return attempt_id


async def test_a_coding_answer_is_judged_by_code_execution_and_completes_the_attempt(client, who, enroll, make_question, make_test, work, code_exec, send_event, sessionmaker):
    test_id, q_code, q_mcq = await code_test(make_question, make_test)
    await enroll()
    attempt_id = await submit_code(client, who, test_id, q_code, q_mcq)
    await work.flush()
    await work.grade()

    result = (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]
    assert result["status"] == "grading" and result["released"] is False  # the code has not been judged yet

    assert await work.dispatch() == 1
    (call,) = code_exec.calls
    reference = f"attempt:{attempt_id}:{q_code}"
    assert call["reference"] == reference and call["priority"] == 2 and call["language"] == "python"
    assert call["problem_id"] == "1755000000006555" and call["source"] == SOLUTION["source"]
    assert call["user_id"] == "1755000000007101"

    await send_event("submission.judged", code_exec.finish(reference, score=100))
    who.student()
    graded = (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]
    assert graded["status"] == "graded" and (graded["score"], graded["max_score"]) == (12, 12) and graded["result"] == "passed"
    assert len(await outbox(sessionmaker, "attempt.finalized")) == 1


async def test_partial_credit_follows_the_weighted_score(client, who, enroll, make_question, make_test, work, code_exec, send_event):
    test_id, q_code, q_mcq = await code_test(make_question, make_test)
    await enroll()
    attempt_id = await submit_code(client, who, test_id, q_code, q_mcq)
    await work.everything()
    await send_event("submission.judged", code_exec.finish(f"attempt:{attempt_id}:{q_code}", score=50, verdict="wrong_answer"))
    who.student()
    result = (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]
    assert (result["score"], result["percent"]) == (7, 58.33)  # 5 of 10 for the code + 2 for the quiz question


async def test_a_redelivered_verdict_is_applied_once(client, who, enroll, make_question, make_test, work, code_exec, send_event, sessionmaker):
    test_id, q_code, q_mcq = await code_test(make_question, make_test)
    await enroll()
    attempt_id = await submit_code(client, who, test_id, q_code, q_mcq)
    await work.everything()
    payload = code_exec.finish(f"attempt:{attempt_id}:{q_code}", score=100)
    await send_event("submission.judged", payload, event_id="same-event-id")
    await send_event("submission.judged", payload, event_id="same-event-id")
    assert len(await outbox(sessionmaker, "attempt.graded")) == 1


async def test_verdicts_for_other_references_are_ignored(client, who, send_event, sessionmaker):
    await send_event("submission.judged", {"reference": "somebody-elses", "submission_id": "1755000000009999", "score": 100, "verdict": "accepted"})
    await send_event("submission.judged", {"reference": None, "submission_id": "1755000000009998", "score": 100, "verdict": "accepted"})
    async with sessionmaker() as db:
        assert (await db.execute(select(CodingSubmission))).scalars().all() == []


async def test_a_missed_event_is_recovered_by_asking_code_execution_directly(client, who, enroll, make_question, make_test, work, code_exec, sessionmaker):
    test_id, q_code, q_mcq = await code_test(make_question, make_test)
    await enroll()
    attempt_id = await submit_code(client, who, test_id, q_code, q_mcq)
    await work.everything()
    code_exec.finish(f"attempt:{attempt_id}:{q_code}", score=100)  # judged, but the event never arrives
    assert await work.reconcile() == 0  # not due yet
    async with sessionmaker() as db:
        await db.execute(update(CodingSubmission).values(available_at=utcnow() - timedelta(seconds=1)))
        await db.commit()
    assert await work.reconcile() == 1
    who.student()
    assert (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]["status"] == "graded"


async def test_a_temporarily_unavailable_engine_is_retried_with_backoff(client, who, enroll, make_question, make_test, work, code_exec, sessionmaker):
    test_id, q_code, q_mcq = await code_test(make_question, make_test)
    await enroll()
    await submit_code(client, who, test_id, q_code, q_mcq)
    await work.flush()
    await work.grade()
    code_exec.fail_with = 503
    assert await work.dispatch() == 1
    async with sessionmaker() as db:
        row = (await db.execute(select(CodingSubmission))).scalar_one()
        assert row.status == "pending" and row.dispatch_attempts == 1 and row.available_at > utcnow()
        await db.execute(update(CodingSubmission).values(available_at=utcnow() - timedelta(seconds=1)))
        await db.commit()
    code_exec.fail_with = None
    assert await work.dispatch() == 1
    async with sessionmaker() as db:
        assert (await db.execute(select(CodingSubmission.status))).scalar_one() == "dispatched"
    assert len({c["reference"] for c in code_exec.calls}) == 1  # the retry carries the same reference, so it is never judged twice


async def test_an_answer_that_cannot_be_judged_goes_to_a_person(client, who, enroll, make_question, make_test, work, code_exec):
    test_id, q_code, q_mcq = await code_test(make_question, make_test)
    await enroll()
    attempt_id = await submit_code(client, who, test_id, q_code, q_mcq)
    await work.flush()
    await work.grade()
    code_exec.fail_with = 404  # e.g. the problem was retired: this can never succeed
    await work.dispatch()

    who.exam_manager()
    queue = (await client.get("/api/v1/grading/queue")).json()["items"]
    assert [(i["attempt_id"], i["question_id"], i["question_type"]) for i in queue] == [(attempt_id, q_code, "coding")]
    assert queue[0]["response"]["source"] == SOLUTION["source"]
    graded = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_code}/grade", json={"marks": 8, "feedback": "Ran it by hand"})
    assert graded.status_code == 200 and graded.json()["attempt"]["status"] == "graded"
    assert graded.json()["attempt"]["score"] == 10


async def test_no_verdict_for_too_long_is_given_up_on(client, who, enroll, make_question, make_test, work, code_exec, sessionmaker):
    test_id, q_code, q_mcq = await code_test(make_question, make_test)
    await enroll()
    attempt_id = await submit_code(client, who, test_id, q_code, q_mcq)
    await work.everything()
    async with sessionmaker() as db:
        await db.execute(update(CodingSubmission).values(available_at=utcnow() - timedelta(seconds=1), dispatched_at=utcnow() - timedelta(hours=2)))
        await db.commit()
    await work.reconcile()
    async with sessionmaker() as db:
        row = (await db.execute(select(CodingSubmission))).scalar_one()
        assert row.status == "failed" and "no verdict" in row.last_error
        answer = (await db.execute(select(AttemptAnswer).where(AttemptAnswer.question_public_id == int(q_code)))).scalar_one()
        assert answer.grading_status == "pending_manual"  # a person decides; the attempt is not left hanging
    assert attempt_id


async def test_flagged_similarity_is_reported_for_reviewers(client, who, enroll, make_question, make_test, work, code_exec, send_event):
    test_id, q_code, q_mcq = await code_test(make_question, make_test)
    await enroll()
    attempt_id = await submit_code(client, who, test_id, q_code, q_mcq)
    await work.everything()
    await send_event("submission.judged", code_exec.finish(f"attempt:{attempt_id}:{q_code}", score=100, flagged=True))
    who.exam_manager()
    report = (await client.get(f"/api/v1/tests/{test_id}/plagiarism")).json()["flagged"]
    assert [(r["attempt_id"], r["question_id"], r["similarity_percent"]) for r in report] == [(attempt_id, q_code, 90)]
    assert (await client.get("/api/v1/attempts", params={"plagiarism_flagged": "true"})).json()["page_context"]["total_records"] == 1
    who.student()
    assert (await client.get(f"/api/v1/tests/{test_id}/plagiarism")).status_code == 403


# ----------------------------------------------------------------------------- manual grading


async def subjective_test(make_question, make_test):
    q_sub = await make_question(subjective(), default_marks=10)
    q_tf = await make_question(true_false(True), default_marks=2)
    test_id = await make_test([fixed(q_sub, 10), fixed(q_tf, 2)], kind="module", target_id=str(MODULE))
    return test_id, q_sub, q_tf


async def take(client, who, test_id, answers):
    who.student()
    attempt_id = (await client.post(f"/api/v1/tests/{test_id}/attempts", json={"start_now": True})).json()["attempt"]["attempt_id"]
    for question_id, response in answers.items():
        assert (await client.put(f"/api/v1/attempts/{attempt_id}/answers/{question_id}", json={"response": response, "revision": 1})).status_code == 200
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    return attempt_id


async def test_a_subjective_answer_waits_for_a_rubric_grade_then_completes_the_attempt(client, who, enroll, make_question, make_test, work):
    test_id, q_sub, q_tf = await subjective_test(make_question, make_test)
    await enroll()
    attempt_id = await take(client, who, test_id, {q_sub: {"text": "A function that calls itself."}, q_tf: {"value": True}})
    await work.everything()
    who.student()
    assert (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]["status"] == "grading"

    who.staff()  # the student's own institution staff
    queue = (await client.get("/api/v1/grading/queue")).json()
    assert [(i["question_id"], i["marks"]) for i in queue["items"]] == [(q_sub, 10)]
    assert [c["id"] for c in queue["items"][0]["rubric"]] == ["clarity", "depth"]

    too_high = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_sub}/grade", json={"rubric_scores": {"clarity": 9, "depth": 1}})
    assert too_high.status_code == 422 and too_high.json()["details"][0]["code"] == "OUT_OF_RANGE"
    unknown = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_sub}/grade", json={"rubric_scores": {"style": 1}})
    assert unknown.status_code == 422
    both = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_sub}/grade", json={"rubric_scores": {"clarity": 1}, "marks": 2})
    assert both.status_code == 422

    graded = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_sub}/grade", json={"rubric_scores": {"clarity": 4, "depth": 4}, "feedback": "Solid, needs a base case example."})
    assert graded.status_code == 200
    body = graded.json()
    assert body["answer"]["marks_awarded"] == 8 and body["answer"]["grading_status"] == "manual_graded"
    assert (body["attempt"]["status"], body["attempt"]["score"], body["attempt"]["result"]) == ("graded", 10, "passed")

    who.student()
    result = (await client.get(f"/api/v1/attempts/{attempt_id}/result")).json()["result"]
    assert result["result"] == "passed" and result["score"] == 10
    who.staff()
    assert (await client.get("/api/v1/grading/queue")).json()["items"] == []


async def test_staff_of_another_institution_and_students_cannot_grade(client, who, enroll, make_question, make_test, work):
    test_id, q_sub, q_tf = await subjective_test(make_question, make_test)
    await enroll()
    attempt_id = await take(client, who, test_id, {q_sub: {"text": "x y z"}})
    await work.everything()
    who.staff(user_id=1755000000007109, organization_id=1755000000007004)
    assert (await client.get("/api/v1/grading/queue")).json()["items"] == []
    assert (await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_sub}/grade", json={"marks": 10})).status_code == 404
    who.student()
    assert (await client.get("/api/v1/grading/queue")).status_code == 403
    assert (await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_sub}/grade", json={"marks": 10})).status_code == 404


async def test_only_exam_managers_can_override_an_automatic_grade_and_must_say_why(client, who, enroll, make_question, make_test, work):
    test_id, q_sub, q_tf = await subjective_test(make_question, make_test)
    await enroll()
    attempt_id = await take(client, who, test_id, {q_sub: {"text": "words"}, q_tf: {"value": False}})
    await work.everything()
    who.staff()
    denied = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_tf}/grade", json={"marks": 2, "feedback": "Ambiguous wording"})
    assert denied.status_code == 403 and denied.json()["code"] == "OVERRIDE_NOT_ALLOWED"
    who.exam_manager()
    no_reason = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_tf}/grade", json={"marks": 2})
    assert no_reason.status_code == 422
    ok = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_tf}/grade", json={"marks": 2, "feedback": "Ambiguous wording, full marks"})
    assert ok.json()["answer"]["marks_awarded"] == 2
    events = (await client.get(f"/api/v1/attempts/{attempt_id}/events")).json()["events"]
    assert "answer_graded" in [e["event_type"] for e in events]


async def test_a_regrade_keeps_human_grades_and_reapplies_the_result(client, who, enroll, make_question, make_test, work, sessionmaker):
    test_id, q_sub, q_tf = await subjective_test(make_question, make_test)
    await enroll()
    attempt_id = await take(client, who, test_id, {q_sub: {"text": "words"}, q_tf: {"value": True}})
    await work.everything()
    who.exam_manager()
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_sub}/grade", json={"marks": 9})
    again = await client.post(f"/api/v1/attempts/{attempt_id}/regrade")
    assert again.status_code == 200 and again.json()["attempt"]["status"] == "graded"
    async with sessionmaker() as db:
        attempt = (await db.execute(select(Attempt))).scalar_one()
        assert attempt.score == 11 and attempt.finalize_revision == 1  # unchanged outcome: not announced again
    assert len(await outbox(sessionmaker, "attempt.graded")) == 1
    who.staff()
    assert (await client.post(f"/api/v1/attempts/{attempt_id}/regrade")).status_code == 403


# ----------------------------------------------------------------------------- file answers


@pytest.fixture
def s3_bucket(settings):
    with mock_aws():
        client = boto3.client("s3", region_name=settings.AWS_REGION, aws_access_key_id="testing", aws_secret_access_key="testing")
        client.create_bucket(Bucket=settings.S3_BUCKET, CreateBucketConfiguration={"LocationConstraint": settings.AWS_REGION})
        yield client


async def test_a_file_answer_is_uploaded_directly_confirmed_and_graded_by_a_person(client, who, enroll, make_question, make_test, work, s3_bucket, settings):
    q_file = await make_question(
        {"question_type": "file_submission", "text": "Upload your report", "body": {"allowed_extensions": ["pdf"], "max_files": 1, "max_size_mb": 1}, "answer_key": {}},
        default_marks=10,
    )
    test_id = await make_test([fixed(q_file, 10)], kind="module", target_id=str(MODULE), pass_mark_percent=50)
    await enroll()
    who.student()
    attempt_id = (await client.post(f"/api/v1/tests/{test_id}/attempts", json={"start_now": True})).json()["attempt"]["attempt_id"]

    wrong_type = await client.post(f"/api/v1/attempts/{attempt_id}/answers/{q_file}/file-upload-url", json={"filename": "run.exe", "content_type": "application/x-msdownload", "size_bytes": 100})
    assert wrong_type.status_code == 422
    issued = await client.post(f"/api/v1/attempts/{attempt_id}/answers/{q_file}/file-upload-url", json={"filename": "My Report.pdf", "content_type": "application/pdf", "size_bytes": 2048})
    assert issued.status_code == 200, issued.text
    key = issued.json()["file"]["key"]
    assert key.startswith(f"attempts/{attempt_id}/{q_file}/") and "url" in issued.json()["file"]["upload"]

    answer = {"files": [{"key": key, "filename": "My Report.pdf", "size": 2048, "content_type": "application/pdf"}]}
    missing = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_file}", json={"response": answer, "revision": 1})
    assert missing.status_code == 422 and missing.json()["details"][0]["code"] == "FILE_NOT_UPLOADED"  # nothing is in storage yet

    s3_bucket.put_object(Bucket=settings.S3_BUCKET, Key=key, Body=b"%PDF-1.4 report", ContentType="application/pdf")
    saved = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_file}", json={"response": answer, "revision": 1})
    assert saved.status_code == 200, saved.text
    stolen = {"files": [{"key": f"attempts/999/{q_file}/x/y.pdf", "filename": "y.pdf", "size": 10}]}
    assert (await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_file}", json={"response": stolen, "revision": 2})).status_code == 422

    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    await work.everything()
    who.exam_manager()
    link = (await client.get(f"/api/v1/attempts/{attempt_id}/answers/{q_file}/files/0")).json()["file"]
    assert link["filename"] == "My Report.pdf" and key in link["url"]
    assert (await client.get(f"/api/v1/attempts/{attempt_id}/answers/{q_file}/files/3")).status_code == 404
    graded = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q_file}/grade", json={"marks": 9})
    assert graded.json()["attempt"]["result"] == "passed"
    who.student(user_id=1755000000007102)
    assert (await client.get(f"/api/v1/attempts/{attempt_id}/answers/{q_file}/files/0")).status_code == 403  # another student
