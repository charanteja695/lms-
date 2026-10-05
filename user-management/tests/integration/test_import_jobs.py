"""Large imports run in the background and produce a downloadable report."""

import csv
import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.config import get_settings
from app.worker.runner import WorkerContext, run_once
from tests.conftest import API, CapturingEmailSender, Hierarchy

HEADER = "role,email,username,first_name,last_name,phone,employee_code,date_of_birth,admission_number,section,guardian_name,guardian_relationship,guardian_phone"
ROWS = [
    "staff,bulk.staff@example.com,bulk.staff,Bulk,Staff,+919811100001,EMP-BULK1,,,,,,",
    "student,,bulk.kid,Bulk,Kid,,,2013-05-01,ADM/BULK/1,B,Ravi Kid,father,+919811100002",
    "student,,,Broken,Row,,,,,,,,",
]


@pytest.fixture
def job_storage(tmp_path: Path) -> Iterator[Path]:
    settings = get_settings()
    original = settings.JOB_STORAGE_DIR
    settings.JOB_STORAGE_DIR = tmp_path
    try:
        yield tmp_path
    finally:
        settings.JOB_STORAGE_DIR = original


async def test_background_import_creates_users_and_reports_every_row(
    client: AsyncClient, app: FastAPI, hierarchy: Hierarchy, emails: CapturingEmailSender, job_storage: Path
) -> None:
    content = "\n".join([HEADER, *ROWS]).encode()
    queued = await client.post(
        f"{API}/users/import-jobs",
        files={"file": ("students.csv", content, "text/csv")},
        data={"mode": "skip_invalid"},
        headers=hierarchy.head,
    )
    assert queued.status_code == 202, queued.text
    job_id = queued.json()["job"]["job_id"]
    assert queued.json()["job"]["type"] == "user_import"

    worker = WorkerContext(
        settings=get_settings(),
        sessionmaker=app.state.sessionmaker,
        redis=app.state.redis,
        email_sender=app.state.email_sender,
    )
    assert await run_once(worker) is True

    job = (await client.get(f"{API}/jobs/{job_id}", headers=hierarchy.head)).json()["job"]
    assert job["status"] == "completed", job
    assert job["import_summary"] == {
        "dry_run": False,
        "mode": "skip_invalid",
        "total_rows": 3,
        "valid_rows": 2,
        "invalid_rows": 1,
        "created": 2,
    }
    assert not list(job_storage.glob("*.input.csv"))  # the upload is removed after processing
    assert "import has finished" in emails.last_to("head1@example.com").text_body

    report = await client.get(f"{API}/jobs/{job_id}/download", headers=hierarchy.head)
    lines = list(csv.DictReader(io.StringIO(report.text.lstrip("﻿"))))
    created = {line["username"]: line for line in lines if line["result"] == "created"}
    assert set(created) == {"bulk.staff", "bulk.kid"}
    assert created["bulk.kid"]["temporary_password"] and not created["bulk.staff"]["temporary_password"]
    assert {line["row"] for line in lines if line["result"] == "error"} == {"4"}

    listed = (await client.get(f"{API}/users", params={"section": "B"}, headers=hierarchy.head)).json()["users"]
    assert [user["username"] for user in listed] == ["bulk.kid"]


async def test_background_import_rejects_bad_columns_without_retrying(
    client: AsyncClient, app: FastAPI, hierarchy: Hierarchy, job_storage: Path
) -> None:
    queued = await client.post(
        f"{API}/users/import-jobs", files={"file": ("bad.csv", b"name,mail\nA,b", "text/csv")}, headers=hierarchy.head
    )
    job_id = queued.json()["job"]["job_id"]
    worker = WorkerContext(
        settings=get_settings(),
        sessionmaker=app.state.sessionmaker,
        redis=app.state.redis,
        email_sender=app.state.email_sender,
    )
    await run_once(worker)
    job = (await client.get(f"{API}/jobs/{job_id}", headers=hierarchy.head)).json()["job"]
    assert job["status"] == "failed" and "columns" in job["error_message"]

    denied = await client.post(
        f"{API}/users/import-jobs", files={"file": ("x.csv", b"role\n", "text/csv")}, headers=hierarchy.student
    )
    assert denied.status_code == 403
