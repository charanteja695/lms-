from datetime import timedelta

from sqlalchemy import select, update

from app.core.time import utcnow
from app.models.session import MediaAccess, ProctorSession, Snapshot
from tests.conftest import INTERNAL_TOKEN, TEST_STRICT
from tests.integration.test_live_session import event, go_live
from tests.integration.test_precheck_and_session import upload

INTERNAL = {"X-Internal-Service-Token": INTERNAL_TOKEN}


async def strict_session(client, who, tests_published, send_event, s3_bucket, settings) -> str:
    settings.AI_ANALYZER_URL = "http://analyzer.test"
    return await go_live(client, who, tests_published, send_event, s3_bucket, settings, level="strict")


async def breakdown(sessionmaker) -> dict:
    async with sessionmaker() as db:
        return (await db.execute(select(ProctorSession.risk_breakdown))).scalar_one()


async def test_a_snapshot_is_analysed_and_findings_become_risk_scaled_by_confidence(client, who, tests_published, send_event, s3_bucket, settings, work, analyzer_service, sessionmaker):
    session_id = await strict_session(client, who, tests_published, send_event, s3_bucket, settings)
    assert await work.analyze() == 2  # the identity photos taken in the pre-check are analysed too (nothing found)
    snapshot = await upload(client, s3_bucket, settings, session_id, "periodic")
    assert snapshot["analysis_status"] == "pending"
    analyzer_service.findings = [{"type": "phone_detected", "confidence": 0.9}, {"type": "looking_away", "confidence": 0.3}, {"type": "no_face", "confidence": 0.8}]
    assert await work.analyze() == 1 and await work.analyze() == 0

    call = analyzer_service.calls[-1]  # the periodic snapshot's call; the analyzer contract: presigned media, and the student's reference face
    assert call["kind"] == "periodic" and call["level"] == "strict" and call["media_url"].startswith("http") and call["reference_url"]
    points = await breakdown(sessionmaker)
    assert points["phone_detected"] == 18 and points["no_face"] == 8  # weight x confidence
    assert "looking_away" not in points  # below AI_MIN_CONFIDENCE: recorded, scores nothing
    async with sessionmaker() as db:
        row = (await db.execute(select(Snapshot).where(Snapshot.kind == "periodic"))).scalar_one()
        assert row.analysis_status == "done" and row.flagged and len(row.findings) == 3


async def test_an_analyzer_that_finds_nothing_is_recorded_as_looked_and_clean(client, who, tests_published, send_event, s3_bucket, settings, work, analyzer_service, sessionmaker):
    session_id = await strict_session(client, who, tests_published, send_event, s3_bucket, settings)
    await upload(client, s3_bucket, settings, session_id, "periodic")
    await work.analyze()
    async with sessionmaker() as db:
        rows = (await db.execute(select(Snapshot).where(Snapshot.kind != "liveness"))).scalars().all()  # liveness frames are kept for a person
        assert {r.analysis_status for r in rows} == {"done"} and all(r.findings == [] and not r.flagged for r in rows)


async def test_an_unavailable_analyzer_is_retried_with_backoff_then_given_up_on(client, who, tests_published, send_event, s3_bucket, settings, work, analyzer_service, sessionmaker):
    settings.ANALYSIS_MAX_ATTEMPTS = 2
    session_id = await strict_session(client, who, tests_published, send_event, s3_bucket, settings)
    await work.analyze()  # the identity photos
    await upload(client, s3_bucket, settings, session_id, "periodic")
    analyzer_service.fail_with = 503
    await work.analyze()
    async with sessionmaker() as db:
        row = (await db.execute(select(Snapshot).where(Snapshot.kind == "periodic"))).scalar_one()
        assert row.analysis_status == "pending" and row.analysis_attempts == 1 and row.analysis_available_at > utcnow()
        await db.execute(update(Snapshot).values(analysis_available_at=utcnow() - timedelta(seconds=1)))
        await db.commit()
    await work.analyze()
    async with sessionmaker() as db:
        row = (await db.execute(select(Snapshot).where(Snapshot.kind == "periodic"))).scalar_one()
        assert row.analysis_status == "failed" and "gave up" in row.skip_reason


async def test_media_the_analyzer_rejects_is_not_retried(client, who, tests_published, send_event, s3_bucket, settings, work, analyzer_service, sessionmaker):
    session_id = await strict_session(client, who, tests_published, send_event, s3_bucket, settings)
    await work.analyze()
    await upload(client, s3_bucket, settings, session_id, "periodic")
    analyzer_service.fail_with = 422
    await work.analyze()
    async with sessionmaker() as db:
        assert (await db.execute(select(Snapshot.analysis_status).where(Snapshot.kind == "periodic"))).scalar_one() == "failed"


async def test_under_heavy_load_only_some_periodic_snapshots_are_analysed(client, who, tests_published, send_event, s3_bucket, settings, sessionmaker):
    settings.ANALYSIS_BACKLOG_SAMPLING_THRESHOLD = 1
    settings.ANALYSIS_SAMPLE_EVERY = 3
    session_id = await strict_session(client, who, tests_published, send_event, s3_bucket, settings)
    statuses = [(await upload(client, s3_bucket, settings, session_id, "periodic"))["analysis_status"] for _ in range(6)]
    # the backlog (identity photos and the first snapshots) crosses the threshold; from then on only every 3rd is kept for analysis
    assert statuses[2] == "pending" and statuses[5] == "pending"
    assert "skipped" in statuses[3:5]
    async with sessionmaker() as db:
        skipped = (await db.execute(select(Snapshot.skip_reason).where(Snapshot.analysis_status == "skipped", Snapshot.kind != "liveness"))).scalars().all()
    assert set(skipped) == {"sampled out under load"}


async def test_an_async_analysis_worker_can_push_findings_once(client, who, tests_published, send_event, s3_bucket, settings, sessionmaker):
    session_id = await strict_session(client, who, tests_published, send_event, s3_bucket, settings)
    snapshot = await upload(client, s3_bucket, settings, session_id, "periodic")
    url = f"/api/v1/internal/snapshots/{snapshot['snapshot_id']}/findings"
    assert (await client.post(url, json={"findings": []})).status_code == 403  # no service token
    body = {"findings": [{"type": "multiple_faces", "confidence": 0.95, "detail": {"faces": 2}}]}
    assert (await client.post(url, json=body, headers=INTERNAL)).json()["snapshot"]["analysis_status"] == "done"
    assert (await client.post(url, json=body, headers=INTERNAL)).status_code == 200  # a retried push is not scored twice
    points = await breakdown(sessionmaker)
    assert points["multiple_faces"] == 24  # 25 x 0.95, once
    async with sessionmaker() as db:
        assert (await db.execute(select(ProctorSession.critical))).scalar_one() is True
    assert (await client.post("/api/v1/internal/snapshots/1755000000001111/findings", json={"findings": []}, headers=INTERNAL)).status_code == 404


async def test_unknown_or_unallowed_finding_types_score_nothing(client, who, tests_published, send_event, s3_bucket, settings, sessionmaker):
    session_id = await strict_session(client, who, tests_published, send_event, s3_bucket, settings)
    snapshot = await upload(client, s3_bucket, settings, session_id, "periodic")
    body = {"findings": [{"type": "tab_switch", "confidence": 1.0}, {"type": "made_up", "confidence": 1.0}]}
    await client.post(f"/api/v1/internal/snapshots/{snapshot['snapshot_id']}/findings", json=body, headers=INTERNAL)
    assert "tab_switch" not in await breakdown(sessionmaker) and "made_up" not in await breakdown(sessionmaker)


async def test_media_past_its_retention_is_deleted_from_storage_and_metadata_survives(client, who, tests_published, send_event, s3_bucket, settings, work, sessionmaker):
    session_id = await strict_session(client, who, tests_published, send_event, s3_bucket, settings)
    kept = await upload(client, s3_bucket, settings, session_id, "periodic")
    old = await upload(client, s3_bucket, settings, session_id, "periodic")
    async with sessionmaker() as db:
        row = (await db.execute(select(Snapshot).where(Snapshot.public_id == int(old["snapshot_id"])))).scalar_one()
        key = row.s3_key
        assert row.delete_after > utcnow() + timedelta(days=89)  # 90 days by default
        row.delete_after = utcnow() - timedelta(seconds=1)
        await db.commit()
    await work.housekeeping()
    assert "Contents" not in s3_bucket.list_objects_v2(Bucket=settings.S3_BUCKET, Prefix=key)  # gone from storage
    async with sessionmaker() as db:
        gone = (await db.execute(select(Snapshot).where(Snapshot.public_id == int(old["snapshot_id"])))).scalar_one()
        live = (await db.execute(select(Snapshot).where(Snapshot.public_id == int(kept["snapshot_id"])))).scalar_one()
        assert gone.deleted_at is not None and gone.s3_key is None and live.deleted_at is None and live.s3_key


async def test_an_expired_snapshot_is_never_analysed(client, who, tests_published, send_event, s3_bucket, settings, work, analyzer_service, sessionmaker):
    session_id = await strict_session(client, who, tests_published, send_event, s3_bucket, settings)
    await upload(client, s3_bucket, settings, session_id, "periodic")
    async with sessionmaker() as db:
        await db.execute(update(Snapshot).values(delete_after=utcnow() - timedelta(seconds=1)))
        await db.commit()
    await work.housekeeping()
    assert await work.analyze() == 0 and analyzer_service.calls == []
    assert MediaAccess and TEST_STRICT and event
