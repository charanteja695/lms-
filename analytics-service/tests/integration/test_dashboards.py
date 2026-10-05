"""The seven dashboards, end to end: an event ingested, rolled up, and read back through the API — and who
may see what (docs/PRODUCT.md §5.9)."""

from tests.conftest import API, EMPLOYER, EMPLOYER_2, INSTITUTION, INSTITUTION_2

APPLICATION_JOB = 1755000000130011


async def test_an_institution_sees_only_its_own_numbers(client, who, send_event, rollup):
    await send_event("enrollment.created", {"enrollment_id": "1", "batch_id": "1", "student_user_id": "1", "organization_id": str(INSTITUTION)})
    await send_event("enrollment.created", {"enrollment_id": "2", "batch_id": "1", "student_user_id": "2", "organization_id": str(INSTITUTION_2)})
    await rollup()

    who.head()  # defaults to INSTITUTION
    response = await client.get(f"{API}/dashboards/institution")
    assert response.status_code == 200, response.text
    body = response.json()["dashboard"]
    assert body["organization_id"] == str(INSTITUTION) and body["enrollments"] == 1


async def test_an_institution_cannot_read_another_institutions_dashboard(client, who):
    who.head()  # INSTITUTION
    response = await client.get(f"{API}/dashboards/institution", params={"organization_id": str(INSTITUTION_2)})
    assert response.status_code == 403 and response.json()["code"] == "NOT_YOUR_ORGANIZATION"


async def test_a_careers_manager_or_analyst_can_read_any_institution(client, who, send_event, rollup):
    await send_event("enrollment.created", {"enrollment_id": "1", "batch_id": "1", "student_user_id": "1", "organization_id": str(INSTITUTION)})
    await rollup()
    who.analyst()
    response = await client.get(f"{API}/dashboards/institution", params={"organization_id": str(INSTITUTION)})
    assert response.status_code == 200 and response.json()["dashboard"]["enrollments"] == 1


async def test_a_platform_dashboard_needs_its_own_scope_or_the_catch_all(client, who):
    who.other_admin()  # holds only accounts.manage
    for path in ("content", "exam-integrity", "support", "hiring", "ai-usage", "billing"):
        response = await client.get(f"{API}/dashboards/{path}")
        assert response.status_code == 403, path

    who.content_admin()
    assert (await client.get(f"{API}/dashboards/content")).status_code == 200
    who.exams_admin()
    assert (await client.get(f"{API}/dashboards/exam-integrity")).status_code == 200
    who.support_admin()
    assert (await client.get(f"{API}/dashboards/support")).status_code == 200
    who.careers_admin()
    assert (await client.get(f"{API}/dashboards/hiring")).status_code == 200
    who.ai_admin()
    assert (await client.get(f"{API}/dashboards/ai-usage")).status_code == 200
    who.billing_admin()
    assert (await client.get(f"{API}/dashboards/billing")).status_code == 200
    who.analyst()  # the catch-all works for every one of them
    for path in ("content", "exam-integrity", "support", "hiring", "ai-usage", "billing"):
        assert (await client.get(f"{API}/dashboards/{path}")).status_code == 200, path


async def test_the_content_dashboard_computes_a_pass_rate_platform_wide(client, who, send_event, rollup):
    await send_event("course.passed", {"course_id": "1", "enrollment_id": "1", "student_user_id": "1", "score": 80, "max_score": 100, "percent": 80.0, "best_percent": 80.0})
    await send_event("course.passed", {"course_id": "1", "enrollment_id": "2", "student_user_id": "2", "score": 90, "max_score": 100, "percent": 90.0, "best_percent": 90.0})
    await send_event("course.failed", {"course_id": "1", "enrollment_id": "3", "student_user_id": "3", "percent": 30.0, "best_percent": 30.0, "attempts_used": 3})
    await rollup()
    who.content_admin()
    body = (await client.get(f"{API}/dashboards/content")).json()["dashboard"]
    assert body["courses_passed"] == 2 and body["courses_failed"] == 1 and body["course_pass_rate"] == round(2 / 3, 3)
    assert body["average_pass_percent"] == 85.0


async def test_an_employer_sees_only_its_own_hiring_funnel_by_default(client, who, send_event, rollup):
    await send_event("application.stage_changed", {"application_id": "1", "job_id": str(APPLICATION_JOB), "employer_id": str(EMPLOYER), "user_id": "1", "organization_id": None, "from": "applied", "to": "shortlisted", "actor": "recruiter"})
    await send_event("application.stage_changed", {"application_id": "2", "job_id": "2", "employer_id": str(EMPLOYER_2), "user_id": "2", "organization_id": None, "from": "applied", "to": "shortlisted", "actor": "recruiter"})
    await rollup()

    who.recruiter()  # EMPLOYER
    body = (await client.get(f"{API}/dashboards/hiring")).json()["dashboard"]
    assert body["employer_id"] == str(EMPLOYER) and body["applications_by_stage"] == {"shortlisted": 1}


async def test_a_recruiter_cannot_read_another_employers_hiring_funnel(client, who):
    who.recruiter()  # EMPLOYER
    response = await client.get(f"{API}/dashboards/hiring", params={"employer_id": str(EMPLOYER_2)})
    assert response.status_code == 403


async def test_the_billing_dashboard_is_wired_but_empty_until_billing_service_exists(client, who, rollup):
    await rollup()
    who.billing_admin()
    body = (await client.get(f"{API}/dashboards/billing")).json()["dashboard"]
    assert body["invoices_issued"] == 0 and body["invoiced_amount"] == 0.0


async def test_the_billing_dashboard_totals_billing_services_real_events(client, who, send_event, rollup):
    org = str(INSTITUTION)
    await send_event("invoice.issued", {"invoice_id": "1", "number": "INV/2026-27/000001", "organization_id": org, "kind": "subscription", "status": "issued", "total_amount": 118000000})
    await send_event("invoice.issued", {"invoice_id": "2", "number": "INV/2026-27/000002", "organization_id": org, "kind": "subscription", "status": "issued", "total_amount": 5900000})
    await send_event("invoice.paid", {"invoice_id": "1", "number": "INV/2026-27/000001", "organization_id": org, "kind": "subscription", "status": "paid", "total_amount": 118000000})
    await send_event("credit_note.issued", {"credit_note_id": "1", "number": "CN/2026-27/000001", "invoice_id": "2", "organization_id": org, "amount": 1180})
    await send_event("plan.activated", {"plan_id": "1", "employer_id": str(EMPLOYER), "organization_id": str(EMPLOYER), "tier": "growth", "job_posts": 10})
    await rollup()
    who.billing_admin()
    body = (await client.get(f"{API}/dashboards/billing")).json()["dashboard"]
    assert (body["invoices_issued"], body["invoiced_amount"], body["invoices_paid"], body["paid_amount"]) == (2, 123900000.0, 1, 118000000.0)
    assert (body["credit_notes"], body["credit_amount"], body["plans_activated"]) == (1, 1180.0, 1)
    scoped = (await client.get(f"{API}/dashboards/billing", params={"organization_id": org})).json()["dashboard"]
    assert scoped["invoices_issued"] == 2 and scoped["plans_activated"] == 0  # the plan belongs to the employer, not this institution
