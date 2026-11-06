"""Background export jobs, the worker and event publishing."""

import csv
import io
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.config import get_settings
from app.worker.runner import WorkerContext, housekeeping, run_once
from tests.conftest import API, CapturingEmailSender, Hierarchy, staff_payload


@pytest.fixture
def job_storage(tmp_path: Path) -> Iterator[Path]:
    settings = get_settings()
    original = settings.JOB_STORAGE_DIR
    settings.JOB_STORAGE_DIR = tmp_path
    try:
        yield tmp_path
    finally:
        settings.JOB_STORAGE_DIR = original


def _worker(app: FastAPI) -> WorkerContext:
    return WorkerContext(
        settings=get_settings(),
        sessionmaker=app.state.sessionmaker,
        redis=app.state.redis,
        email_sender=app.state.email_sender,
    )


async def test_export_job_lifecycle(
    client: AsyncClient, app: FastAPI, hierarchy: Hierarchy, emails: CapturingEmailSender, job_storage: Path
) -> None:
    queued = await client.post(f"{API}/users/export-jobs", params={"role": "student"}, headers=hierarchy.head)
    assert queued.status_code == 202, queued.text
    job = queued.json()["job"]
    assert job["status"] == "queued" and job["download_url"] is None

    not_ready = await client.get(f"{API}/jobs/{job['job_id']}/download", headers=hierarchy.head)
    assert not_ready.json()["code"] == "JOB_NOT_READY"

    assert await run_once(_worker(app)) is True

    done = (await client.get(f"{API}/jobs/{job['job_id']}", headers=hierarchy.head)).json()["job"]
    assert done["status"] == "completed"
    assert done["row_count"] == 1
    assert done["download_url"].endswith(f"/jobs/{job['job_id']}/download")
    assert "export is ready" in emails.last_to("head1@example.com").text_body

    download = await client.get(f"{API}/jobs/{job['job_id']}/download", headers=hierarchy.head)
    assert download.status_code == 200
    rows = list(csv.DictReader(io.StringIO(download.text.lstrip("﻿"))))
    assert [r["user_id"] for r in rows] == [hierarchy.student_id]

    # Jobs are private to the requester.
    assert (await client.get(f"{API}/jobs/{job['job_id']}", headers=hierarchy.admin)).status_code == 404
    listed = (await client.get(f"{API}/jobs", headers=hierarchy.head)).json()
    assert [j["job_id"] for j in listed["jobs"]] == [job["job_id"]]


async def test_export_job_validates_permissions_up_front_and_at_run_time(
    client: AsyncClient, app: FastAPI, hierarchy: Hierarchy, job_storage: Path
) -> None:
    assert (await client.post(f"{API}/users/export-jobs", headers=hierarchy.student)).status_code == 403
    assert (await client.post(f"{API}/admins/export-jobs", headers=hierarchy.admin)).status_code == 403

    queued = (await client.post(f"{API}/institutions/export-jobs", headers=hierarchy.head)).json()["job"]
    # The head is suspended before the worker runs: the job must fail, not leak data.
    await client.patch(f"{API}/users/{hierarchy.head_id}/status", json={"status": "suspended"}, headers=hierarchy.admin)
    await run_once(_worker(app))
    async with app.state.sessionmaker() as db:
        from sqlalchemy import select

        from app.models import BackgroundJob

        job = (await db.execute(select(BackgroundJob))).scalar_one()
    assert str(job.public_id) == queued["job_id"]
    assert job.status == "failed"
    assert not list(job_storage.glob("*.csv"))


async def test_expired_exports_are_removed(
    client: AsyncClient, app: FastAPI, hierarchy: Hierarchy, job_storage: Path
) -> None:
    from sqlalchemy import update

    from app.core.time import utcnow
    from app.models import BackgroundJob

    job = (await client.post(f"{API}/admins/export-jobs", headers=hierarchy.root)).json()["job"]
    worker = _worker(app)
    await run_once(worker)
    assert len(list(job_storage.glob("*.csv"))) == 1

    async with app.state.sessionmaker() as db:
        await db.execute(update(BackgroundJob).values(expires_at=utcnow()))
        await db.commit()
    await housekeeping(worker)
    status = (await client.get(f"{API}/jobs/{job['job_id']}", headers=hierarchy.root)).json()["job"]["status"]
    assert status == "expired"
    assert not list(job_storage.glob("*.csv"))


async def test_events_are_published_to_the_stream(client: AsyncClient, app: FastAPI, hierarchy: Hierarchy) -> None:
    created = (await client.post(f"{API}/users", json=staff_payload("event.staff"), headers=hierarchy.head)).json()[
        "user"
    ]
    await run_once(_worker(app))

    stream = get_settings().EVENTS_STREAM
    entries = await app.state.redis.xrange(stream)
    types = [fields["event_type"] for _, fields in entries]
    assert types.count("user.created") == 5  # admin, head, staff, student from the fixture + this one
    assert "institution.created" in types

    last_created = [fields for _, fields in entries if fields["event_type"] == "user.created"][-1]
    payload = json.loads(last_created["payload"])
    assert payload["user_id"] == created["user_id"]
    assert payload["organization_id"] == hierarchy.organization_id
    assert "-" not in last_created["event_id"]  # hex id, no internal UUID formatting

    # Nothing is published twice.
    await run_once(_worker(app))
    assert len(await app.state.redis.xrange(stream)) == len(entries)


async def test_event_publishing_retries_after_failure(client: AsyncClient, app: FastAPI, hierarchy: Hierarchy) -> None:
    from sqlalchemy import func, select

    from app.events.publisher import relay_outbox
    from app.models import OutboxEvent

    class BrokenPublisher:
        async def publish(self, event: OutboxEvent) -> None:
            raise ConnectionError("broker down")

    assert await relay_outbox(app.state.sessionmaker, BrokenPublisher(), batch_size=50) == 0
    async with app.state.sessionmaker() as db:
        pending = (
            await db.execute(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.published_at.is_(None)))
        ).scalar_one()
        attempts = (await db.execute(select(func.max(OutboxEvent.attempts)))).scalar_one()
    assert pending > 0 and attempts == 1

    await run_once(_worker(app))
    async with app.state.sessionmaker() as db:
        still_pending = (
            await db.execute(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.published_at.is_(None)))
        ).scalar_one()
    assert still_pending == 0
