from datetime import timedelta

from sqlalchemy import select, update

from app.core.time import utcnow
from app.models.certificate import Certificate
from app.models.outbox_event import OutboxEvent
from tests.conftest import ATTEMPT, COURSE, ORG_A, ORG_B, STAFF_A, STAFF_B, STUDENT, STUDENT_2, VERSION, passed_payload


async def outbox(sessionmaker, event_type: str) -> list[dict]:
    async with sessionmaker() as db:
        rows = (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == event_type).order_by(OutboxEvent.created_at))).scalars()
        return [row.payload for row in rows]


async def issue(send_event, directory, **kwargs) -> None:
    await directory()
    await send_event("course.passed", passed_payload(**kwargs))


async def my_certificate(client, who) -> dict:
    who.student()
    (certificate,) = (await client.get("/api/v1/certificates")).json()["certificates"]
    return certificate


async def test_a_pass_issues_a_certificate_with_everything_printed_snapshotted(client, who, send_event, directory, sessionmaker):
    await issue(send_event, directory)
    certificate = await my_certificate(client, who)
    assert certificate["status"] == "issued" and certificate["pdf_status"] == "pending"
    assert certificate["student_name"] == "Aarav Reddy" and certificate["course_title"] == "Full Stack Development with MERN"
    assert certificate["institution_name"] == "Springfield High"
    assert certificate["score_percent"] == 91.5 and certificate["grade"] == "Distinction"
    assert certificate["completion_date"] == "2026-09-21T10:30:00Z"
    assert certificate["verification_url"] == f"https://lms.example/verify/{certificate['verification_code']}"
    assert certificate["verification_code"] != certificate["certificate_id"] and len(certificate["verification_code"]) >= 12
    assert f"certId={certificate['certificate_id']}" in certificate["linkedin_add_url"] and "linkedin.com/profile/add" in certificate["linkedin_add_url"]

    (event,) = await outbox(sessionmaker, "certificate.issued")
    assert event["certificate_id"] == certificate["certificate_id"] and event["student_user_id"] == str(STUDENT)
    assert event["course_id"] == str(COURSE) and event["version_id"] == str(VERSION) and event["grade"] == "Distinction"


async def test_grade_follows_the_score(client, who, send_event, directory):
    await directory()
    await send_event("course.passed", passed_payload(percent=72))
    assert (await my_certificate(client, who))["grade"] == "Merit"


async def test_a_redelivered_event_and_a_second_pass_do_not_issue_twice(client, who, send_event, directory, sessionmaker):
    await directory()
    await send_event("course.passed", passed_payload(), event_id="evt-1")
    await send_event("course.passed", passed_payload(), event_id="evt-1")  # redelivery
    await send_event("course.passed", passed_payload(), event_id="evt-2")  # the same attempt announced again
    await send_event("course.passed", passed_payload(attempt=ATTEMPT + 1), event_id="evt-3")  # another pass for a course already certified
    who.student()
    assert (await client.get("/api/v1/certificates")).json()["page_context"]["total_records"] == 1
    assert len(await outbox(sessionmaker, "certificate.issued")) == 1


async def test_the_pdf_is_rendered_once_stored_and_downloadable(client, who, send_event, directory, render, s3_bucket, settings):
    await issue(send_event, directory)
    certificate = await my_certificate(client, who)
    assert (await client.get(f"/api/v1/certificates/{certificate['certificate_id']}/download")).json()["code"] == "PDF_NOT_READY"

    assert await render() == 1
    assert await render() == 0  # generated once
    who.student()
    ready = (await client.get(f"/api/v1/certificates/{certificate['certificate_id']}")).json()["certificate"]
    assert ready["pdf_status"] == "ready"
    link = (await client.get(f"/api/v1/certificates/{certificate['certificate_id']}/download")).json()["download"]
    assert link["filename"] == f"certificate-{certificate['certificate_id']}.pdf" and "certificate.pdf" in link["url"]
    stored = s3_bucket.get_object(Bucket=settings.S3_BUCKET, Key=f"certificates/{certificate['certificate_id']}/certificate.pdf")["Body"].read()
    assert stored.startswith(b"%PDF-") and len(stored) > 2_000


async def test_details_that_have_not_arrived_yet_delay_the_pdf_instead_of_printing_blanks(client, who, send_event, render, sessionmaker):
    await send_event("course.passed", passed_payload())  # the user and course events are still in flight
    who.student()
    certificate = (await client.get("/api/v1/certificates")).json()["certificates"][0]
    assert certificate["student_name"] is None
    await render()
    async with sessionmaker() as db:
        row = (await db.execute(select(Certificate))).scalar_one()
        assert row.pdf_status == "pending" and row.pdf_attempts == 1 and "has not arrived" in row.last_error
        assert row.pdf_available_at > utcnow()  # backed off
    assert await render() == 0

    await send_event("user.created", {"user_id": str(STUDENT), "first_name": "Aarav", "last_name": "Reddy", "role": "student"})
    await send_event("course.published", {"course_id": str(COURSE), "title": "Full Stack Development with MERN"})
    async with sessionmaker() as db:
        await db.execute(update(Certificate).values(pdf_available_at=utcnow() - timedelta(seconds=1)))
        await db.commit()
    assert await render() == 1
    who.student()
    ready = (await client.get(f"/api/v1/certificates/{certificate['certificate_id']}")).json()["certificate"]
    assert ready["pdf_status"] == "ready" and ready["student_name"] == "Aarav Reddy"


async def test_a_pdf_that_keeps_failing_is_marked_failed_and_can_be_regenerated(client, who, send_event, render, sessionmaker, settings):
    settings.PDF_MAX_ATTEMPTS = 2
    await send_event("course.passed", passed_payload())
    for _ in range(2):
        await render()
        async with sessionmaker() as db:
            await db.execute(update(Certificate).where(Certificate.pdf_status == "pending").values(pdf_available_at=utcnow() - timedelta(seconds=1)))
            await db.commit()
    async with sessionmaker() as db:
        assert (await db.execute(select(Certificate.pdf_status))).scalar_one() == "failed"

    who.exam_manager()
    (certificate,) = (await client.get("/api/v1/certificates", params={"pdf_status": "failed"})).json()["certificates"]
    await send_event("user.created", {"user_id": str(STUDENT), "first_name": "Aarav", "last_name": "Reddy", "role": "student"})
    await send_event("course.published", {"course_id": str(COURSE), "title": "MERN"})
    regenerated = await client.post(f"/api/v1/certificates/{certificate['certificate_id']}/regenerate-pdf")
    assert regenerated.json()["certificate"]["pdf_status"] == "pending"
    await render()
    assert (await client.get(f"/api/v1/certificates/{certificate['certificate_id']}")).json()["certificate"]["pdf_status"] == "ready"


async def test_the_public_page_needs_no_login_and_reveals_only_what_is_printed(client, who, send_event, directory, app):
    await issue(send_event, directory)
    code = (await my_certificate(client, who))["verification_code"]
    app.dependency_overrides.pop(__import__("app.api.deps", fromlist=["_authenticate"])._authenticate, None)  # no token at all
    response = await client.get(f"/api/v1/public/verify/{code}")
    assert response.status_code == 200
    verification = response.json()["verification"]
    assert verification["valid"] is True and verification["status"] == "issued"
    assert verification["student_name"] == "Aarav Reddy" and verification["course_title"] == "Full Stack Development with MERN"
    assert verification["issuer"] == "LMS" and verification["grade"] == "Distinction"
    assert not {"student_user_id", "organization_id", "attempt_id", "verification_code"} & verification.keys()
    assert (await client.get("/api/v1/public/verify/not-a-real-code")).status_code == 404


async def test_a_lost_integrity_case_revokes_the_certificate_and_the_page_says_so(client, who, send_event, directory, sessionmaker):
    await issue(send_event, directory)
    certificate = await my_certificate(client, who)
    await send_event("course.pass_revoked", {"attempt_id": str(ATTEMPT), "student_user_id": str(STUDENT), "course_id": str(COURSE), "reason": "integrity"})
    await send_event("course.pass_revoked", {"attempt_id": str(ATTEMPT), "student_user_id": str(STUDENT), "course_id": str(COURSE), "reason": "integrity"})

    who.student()
    revoked = (await client.get(f"/api/v1/certificates/{certificate['certificate_id']}")).json()["certificate"]
    assert revoked["status"] == "revoked" and revoked["revoked_at"]
    page = (await client.get(f"/api/v1/public/verify/{certificate['verification_code']}")).json()
    assert page["verification"]["valid"] is False and page["verification"]["status"] == "revoked" and page["verification"]["revoked_at"]
    assert "integrity" not in str(page).lower()  # the public page never says why
    (event,) = await outbox(sessionmaker, "certificate.revoked")  # once, despite the redelivery
    assert event["certificate_id"] == certificate["certificate_id"] and "Integrity" in event["reason"]


async def test_a_revoked_pdf_is_not_handed_to_the_student_but_staff_can_still_get_it(client, who, send_event, directory, render):
    await issue(send_event, directory)
    certificate = await my_certificate(client, who)
    await render()
    await send_event("course.pass_revoked", {"attempt_id": str(ATTEMPT), "student_user_id": str(STUDENT), "course_id": str(COURSE)})
    who.student()
    denied = await client.get(f"/api/v1/certificates/{certificate['certificate_id']}/download")
    assert denied.status_code == 403 and denied.json()["code"] == "CERTIFICATE_REVOKED"
    who.staff()
    assert (await client.get(f"/api/v1/certificates/{certificate['certificate_id']}/download")).status_code == 200


async def test_a_genuine_later_pass_after_a_revocation_gets_a_new_certificate(client, who, send_event, directory):
    await issue(send_event, directory)
    await send_event("course.pass_revoked", {"attempt_id": str(ATTEMPT), "student_user_id": str(STUDENT), "course_id": str(COURSE)})
    await send_event("course.passed", passed_payload(attempt=ATTEMPT + 5))
    who.student()
    statuses = sorted(c["status"] for c in (await client.get("/api/v1/certificates")).json()["certificates"])
    assert statuses == ["issued", "revoked"]


async def test_exam_managers_can_revoke_with_a_reason_once(client, who, send_event, directory, sessionmaker):
    await issue(send_event, directory)
    certificate = await my_certificate(client, who)
    who.student()
    assert (await client.post(f"/api/v1/certificates/{certificate['certificate_id']}/revoke", json={"reason": "x"})).status_code == 403
    who.exam_manager()
    revoked = await client.post(f"/api/v1/certificates/{certificate['certificate_id']}/revoke", json={"reason": "Issued in error"})
    assert revoked.status_code == 200 and revoked.json()["certificate"]["revoke_reason"] == "Issued in error"
    assert (await client.post(f"/api/v1/certificates/{certificate['certificate_id']}/revoke", json={"reason": "again"})).json()["code"] == "ALREADY_REVOKED"
    events = (await client.get(f"/api/v1/certificates/{certificate['certificate_id']}/events")).json()["events"]
    assert [e["event_type"] for e in events] == ["issued", "revoked"]
    assert len(await outbox(sessionmaker, "certificate.revoked")) == 1


async def test_who_can_see_which_certificates(client, who, send_event, directory):
    await directory()
    await directory(student=STUDENT_2, first="Meera", last="Nair")
    await send_event("course.passed", passed_payload())
    await send_event("course.passed", passed_payload(student=STUDENT_2, attempt=ATTEMPT + 1))
    who.student()
    mine = (await client.get("/api/v1/certificates")).json()["certificates"]
    assert [c["student_user_id"] for c in mine] == [str(STUDENT)]
    other = (await client.get("/api/v1/certificates", params={"user_id": str(STUDENT_2)})).json()["certificates"]
    assert [c["student_user_id"] for c in other] == [str(STUDENT)]  # a student cannot ask for someone else's
    theirs = await client.get(f"/api/v1/certificates/{(await client.get('/api/v1/certificates')).json()['certificates'][0]['certificate_id']}")
    assert theirs.status_code == 200

    who.staff()
    assert (await client.get("/api/v1/certificates")).json()["page_context"]["total_records"] == 2
    who.staff(user_id=STAFF_B, organization_id=1755000000007004)
    assert (await client.get("/api/v1/certificates")).json()["certificates"] == []
    who.exam_manager()
    assert (await client.get("/api/v1/certificates")).json()["page_context"]["total_records"] == 2
    assert (await client.get("/api/v1/certificates", params={"user_id": str(STUDENT_2)})).json()["page_context"]["total_records"] == 1
    who.student(user_id=STUDENT_2)
    other_cert = (await client.get("/api/v1/certificates")).json()["certificates"][0]["certificate_id"]
    who.student()
    assert (await client.get(f"/api/v1/certificates/{other_cert}")).status_code == 404


async def test_the_public_endpoint_is_rate_limited(client, app, settings, send_event, directory, who):
    settings.RATE_LIMIT_ENABLED = True
    settings.PUBLIC_VERIFY_RATE_LIMIT_PER_IP_PER_MINUTE = 3
    await issue(send_event, directory)
    codes = [(await client.get("/api/v1/public/verify/nope")).status_code for _ in range(5)]
    assert codes == [404, 404, 404, 429, 429]
    assert ORG_A


async def test_certificates_follow_the_persons_permissions(client, act_as):
    """A super admin can take the student-certificates list away from one staff member."""
    act_as(STAFF_A, role="staff", organization_id=ORG_A, defaults=False)
    assert (await client.get("/api/v1/certificates")).status_code == 403
    act_as(STAFF_A, role="staff", organization_id=ORG_A)
    assert (await client.get("/api/v1/certificates")).status_code == 200
    act_as(STUDENT, role="student", organization_id=ORG_A, defaults=False)
    assert (await client.get("/api/v1/certificates")).status_code == 403



async def test_staff_export_their_students_certificates_as_csv(client, who, send_event, directory):
    await issue(send_event, directory)
    await send_event("course.passed", passed_payload(student=STUDENT_2, attempt=ATTEMPT + 1, org=ORG_B))

    who.staff()  # ORG_A: their own student only
    export = await client.get("/api/v1/certificates/export")
    assert export.status_code == 200 and export.headers["content-type"].startswith("text/csv")
    lines = export.text.lstrip("﻿").strip().splitlines()
    assert lines[0].startswith("certificate_id,verification_code,verification_url,student_name") and len(lines) == 2

    who.exam_manager()  # everyone's
    assert len((await client.get("/api/v1/certificates/export")).text.strip().splitlines()) == 3
    who.student()
    assert (await client.get("/api/v1/certificates/export")).status_code == 403
