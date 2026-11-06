"""Scheduled reports (docs/PRODUCT.md §5.9 "Scheduled reports"): save one, run it now, download the file, and
the worker picking up a due one."""

from datetime import timedelta

from sqlalchemy import select

from app.core.time import utcnow
from app.models.report import ReportDefinition
from app.services.report_service import run_due_reports
from tests.conftest import API, INSTITUTION


async def test_creating_a_report_for_the_institution_dashboard_needs_an_organization_id(client, who):
    who.head()
    missing = await client.post(f"{API}/reports", json={"name": "Weekly institution report", "dashboard": "institution", "filters": {}})
    assert missing.status_code == 422

    ok = await client.post(f"{API}/reports", json={"name": "Weekly institution report", "dashboard": "institution", "filters": {"organization_id": str(INSTITUTION)}})
    assert ok.status_code == 201, ok.text
    assert ok.json()["report"]["dashboard"] == "institution"


async def test_an_institution_cannot_schedule_a_report_for_another_institution(client, who):
    who.head()  # INSTITUTION
    response = await client.post(f"{API}/reports", json={"name": "Not mine", "dashboard": "institution", "filters": {"organization_id": "1755000000199999"}})
    assert response.status_code == 403


async def test_run_now_renders_a_csv_and_it_can_be_downloaded(client, who, send_event, rollup):
    await send_event("certificate.issued", {"certificate_id": "1", "student_user_id": "1", "organization_id": str(INSTITUTION)})
    await rollup()
    who.head()
    created = await client.post(f"{API}/reports", json={"name": "Certificates", "dashboard": "institution", "filters": {"organization_id": str(INSTITUTION)}})
    report_id = created.json()["report"]["report_id"]

    run = await client.post(f"{API}/reports/{report_id}/run-now")
    assert run.status_code == 201, run.text
    assert run.json()["run"]["status"] == "ready" and run.json()["run"]["row_count"] > 0
    run_id = run.json()["run"]["run_id"]

    download = await client.get(f"{API}/reports/{report_id}/runs/{run_id}/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("text/csv")
    assert b"certificates_issued" in download.content and b"1" in download.content


async def test_a_report_is_not_visible_to_someone_else(client, who, send_event, rollup):
    who.head()
    created = await client.post(f"{API}/reports", json={"name": "Mine", "dashboard": "institution", "filters": {"organization_id": str(INSTITUTION)}})
    report_id = created.json()["report"]["report_id"]

    who.staff()  # a different user, same institution
    hidden = await client.get(f"{API}/reports/{report_id}")
    assert hidden.status_code == 404


async def test_deactivating_a_report_stops_it_being_picked_up_as_due(client, who, sessionmaker, settings):
    who.head()
    created = await client.post(f"{API}/reports", json={"name": "To deactivate", "dashboard": "institution", "filters": {"organization_id": str(INSTITUTION)}})
    report_id = created.json()["report"]["report_id"]
    await client.post(f"{API}/reports/{report_id}/deactivate")

    async with sessionmaker() as db:
        definition = (await db.execute(select(ReportDefinition))).scalar_one()
        definition.next_run_at = utcnow() - timedelta(days=1)  # force it "due"
        await db.commit()

    ran = await run_due_reports(sessionmaker, settings)
    assert ran == 0  # inactive: the worker skips it


async def test_the_worker_runs_a_due_report_and_reschedules_it(client, who, sessionmaker, settings, send_event, rollup):
    await send_event("certificate.issued", {"certificate_id": "1", "student_user_id": "1", "organization_id": str(INSTITUTION)})
    await rollup()
    who.head()
    created = await client.post(f"{API}/reports", json={"name": "Auto-run", "dashboard": "institution", "filters": {"organization_id": str(INSTITUTION)}, "frequency": "daily"})
    report_id = created.json()["report"]["report_id"]

    async with sessionmaker() as db:
        definition = (await db.execute(select(ReportDefinition))).scalar_one()
        definition.next_run_at = utcnow() - timedelta(minutes=1)
        original_next_run = definition.next_run_at
        await db.commit()

    ran = await run_due_reports(sessionmaker, settings)
    assert ran == 1

    async with sessionmaker() as db:
        definition = (await db.execute(select(ReportDefinition))).scalar_one()
        assert definition.next_run_at > original_next_run  # rescheduled for the next day

    runs = await client.get(f"{API}/reports/{report_id}/runs")
    assert runs.json()["runs"][0]["status"] == "ready"
