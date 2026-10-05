from datetime import timedelta

from sqlalchemy import update

from app.core.time import utcnow
from app.domain.enums import JobStatus, Priority
from app.models.run import Run
from app.services.queue_service import QueueService


async def add_runs(sessionmaker, count: int, *, priority: int = Priority.PRACTICE, when=None) -> None:
    async with sessionmaker() as db:
        for n in range(count):
            db.add(Run(public_id=900_000 + n + priority * 1000, user_id=1, language_code="python3", source="print(1)", priority=priority, available_at=when or utcnow()))
        await db.commit()


async def test_claiming_marks_jobs_running_counts_the_attempt_and_leases_them(sessionmaker, settings) -> None:
    await add_runs(sessionmaker, 3)
    async with sessionmaker() as db:
        claimed = await QueueService(db, settings).claim(Run, 2)
    assert [(job.status, job.attempts) for job in claimed] == [(JobStatus.RUNNING, 1)] * 2
    assert all(job.available_at > utcnow() + timedelta(seconds=settings.JOB_LEASE_SECONDS - 5) for job in claimed)

    async with sessionmaker() as db:
        second = await QueueService(db, settings).claim(Run, 10)
    assert len(second) == 1  # the two leased jobs are not handed out again
    assert {job.id for job in second}.isdisjoint({job.id for job in claimed})


async def test_a_lease_that_lapses_returns_the_job_to_the_queue_with_a_higher_attempt_count(sessionmaker, settings) -> None:
    await add_runs(sessionmaker, 1)
    async with sessionmaker() as db:
        [job] = await QueueService(db, settings).claim(Run, 1)  # the worker takes it... and dies
        job_id = job.id
    async with sessionmaker() as db:
        assert await QueueService(db, settings).claim(Run, 1) == []  # still within its lease
        await db.execute(update(Run).values(available_at=utcnow() - timedelta(seconds=1)))
        await db.commit()
    async with sessionmaker() as db:
        [again] = await QueueService(db, settings).claim(Run, 1)
    assert (again.id, again.attempts, again.status) == (job_id, 2, JobStatus.RUNNING)


async def test_finished_and_not_yet_due_jobs_are_never_claimed(sessionmaker, settings) -> None:
    await add_runs(sessionmaker, 2)
    await add_runs(sessionmaker, 1, priority=Priority.SUBMISSION, when=utcnow() + timedelta(minutes=5))
    async with sessionmaker() as db:
        await db.execute(update(Run).where(Run.priority == Priority.PRACTICE).values(status=JobStatus.COMPLETED))
        await db.commit()
    async with sessionmaker() as db:
        assert await QueueService(db, settings).claim(Run, 10) == []


async def test_lanes_are_served_highest_first_and_oldest_first_within_a_lane(sessionmaker, settings) -> None:
    now = utcnow()
    async with sessionmaker() as db:
        for public_id, priority, age in ((1, Priority.PRACTICE, 50), (2, Priority.EXAM, 10), (3, Priority.SUBMISSION, 30), (4, Priority.EXAM, 40), (5, Priority.SUBMISSION, 5)):
            db.add(Run(public_id=public_id, user_id=1, language_code="python3", source="x", priority=priority, available_at=now - timedelta(seconds=age)))
        await db.commit()
    async with sessionmaker() as db:
        claimed = await QueueService(db, settings).claim(Run, 5)
    assert [job.public_id for job in claimed] == [4, 2, 3, 5, 1]


async def test_the_queue_depth_is_counted_per_lane(sessionmaker, settings) -> None:
    await add_runs(sessionmaker, 2, priority=Priority.PRACTICE)
    await add_runs(sessionmaker, 3, priority=Priority.EXAM)
    async with sessionmaker() as db:
        assert await QueueService(db, settings).depth(Run) == {0: 2, 2: 3}
