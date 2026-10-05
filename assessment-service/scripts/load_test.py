"""Load check for the hot paths: preparing/starting attempts, saving answers, flushing them, and grading.

Runs the service layer directly (no HTTP, no auth) against a real PostgreSQL and a fake Redis, so it measures this
service's own overhead: queries, validation, serialisation. It says nothing about a Redis server's or the network's
cost, so treat the numbers as an upper bound for one process and size the deployment from a run against real Redis.

    python scripts/load_test.py --students 300 --questions 20
    python scripts/load_test.py --students 300 --database-url postgresql+asyncpg://lms:lms@localhost:5432/lms_assessment_load

Without --database-url it starts an embedded PostgreSQL with pgserver (pip install pgserver).
"""

import argparse
import asyncio
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import fakeredis.aioredis

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lms_common.auth import AccessTokenClaims  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.context import RequestContext  # noqa: E402
from app.db.session import build_engine, build_sessionmaker  # noqa: E402
from app.domain.enums import SubmitReason  # noqa: E402
from app.events.consumers.directory_events import handle_course_published, handle_enrollment_created  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.attempt import Attempt  # noqa: E402
from app.schemas.question import QuestionCreate  # noqa: E402
from app.schemas.test import SectionIn, SlotIn, TestCreate  # noqa: E402
from app.services.answer_service import AnswerItem, AnswerService  # noqa: E402
from app.services.attempt_service import AttemptService  # noqa: E402
from app.services.grading_service import GradingService  # noqa: E402
from app.services.question_service import QuestionService  # noqa: E402
from app.services.test_service import TestService  # noqa: E402
from app.worker.runner import flush_answers, grade_submitted  # noqa: E402

COURSE, VERSION, MODULE = 1755000000008001, 1755000000008002, 1755000000008003
CTX = RequestContext(ip_address="127.0.0.1", user_agent="load-test", request_id=None)


def claims(user_id: int, role: str = "student", org: int | None = 1755000000007003, scopes: tuple[str, ...] = ()) -> AccessTokenClaims:
    now = datetime.now(UTC)
    return AccessTokenClaims(
        user_id=user_id, session_id=1, role=role, organization_id=org, organization_type="institution" if org else None,
        scopes=scopes, token_version=0, token_id="load", issued_at=int(now.timestamp()), expires_at=now,  # noqa: S106
    )


def percentiles(samples: list[float]) -> str:
    ordered = sorted(samples)
    pick = lambda q: ordered[min(len(ordered) - 1, int(len(ordered) * q))] * 1000  # noqa: E731
    return f"p50 {pick(0.50):.1f} ms  p95 {pick(0.95):.1f} ms  p99 {pick(0.99):.1f} ms  max {ordered[-1] * 1000:.1f} ms"


async def timed(samples: list[float], coroutine):
    started = time.perf_counter()
    result = await coroutine
    samples.append(time.perf_counter() - started)
    return result


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--students", type=int, default=200)
    parser.add_argument("--questions", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--database-url")
    args = parser.parse_args()

    server = None
    url = args.database_url
    if url is None:
        import pgserver

        server = pgserver.get_server(tempfile.mkdtemp(prefix="assessment_load_"), cleanup_mode="delete")
        server.psql("CREATE DATABASE lms_assessment_load;")
        url = server.get_uri().rsplit("/", 1)[0].replace("postgresql://", "postgresql+asyncpg://", 1) + "/lms_assessment_load"

    settings = Settings(ENVIRONMENT="test", DATABASE_URL=url, RATE_LIMIT_ENABLED=False, LOG_JSON=False, DB_POOL_SIZE=20, DB_MAX_OVERFLOW=40, POOL_CACHE_SECONDS=0, WORKER_CONCURRENCY=16)
    engine = build_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = build_sessionmaker(engine)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    admin = claims(1755000000009001, "super_admin", None)

    # ---- seed: a bank of questions, one published test, enrolled students
    async with sessionmaker() as db:
        question_ids = []
        for n in range(args.questions):
            question = await QuestionService(db, settings).create(
                QuestionCreate(
                    question_type="mcq_single", text=f"Question {n}",
                    body={"options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}, {"id": "c", "text": "C"}]},
                    answer_key={"correct": "b"}, skills=["load"],
                ),
                admin,
            )
            await QuestionService(db, settings).submit(question, admin)
            await QuestionService(db, settings).approve(await QuestionService(db, settings).get(question.public_id), admin, None)
            question_ids.append(question.public_id)
        test = await TestService(db, settings, redis).create(
            TestCreate(
                title="Load test", kind="module", target_id=str(MODULE), duration_minutes=60, max_attempts=0, shuffle_options=True, shuffle_questions=True,
                sections=[SectionIn(title="All", slots=[SlotIn(slot_type="pool", count=args.questions, marks=1, criteria={"skills": ["load"]})])],
            ),
            admin,
        )
        await TestService(db, settings, redis).submit(test, admin)
        test = await TestService(db, settings, redis).approve(await TestService(db, settings, redis).load(test.public_id), admin, None)
        await handle_course_published(db, {"course_id": str(COURSE), "version_id": str(VERSION), "modules": [{"module_id": str(MODULE), "topics": []}]})
        students = [1755000000100000 + n for n in range(args.students)]
        for n, student in enumerate(students):
            await handle_enrollment_created(db, {"enrollment_id": str(1755000000200000 + n), "student_user_id": str(student), "organization_id": "1755000000007003", "version_id": str(VERSION)})
        await db.commit()
    test_id = test.public_id

    gate = asyncio.Semaphore(args.concurrency)
    prepare_times: list[float] = []
    start_times: list[float] = []
    save_times: list[float] = []
    attempt_ids: list[int] = []

    async def student_session(student: int) -> None:
        auth = claims(student)
        async with gate:
            async with sessionmaker() as db:
                service = AttemptService(db, settings, redis)
                test_row = await TestService(db, settings, redis).load(test_id)
                attempt = await timed(prepare_times, service.prepare(test_row, auth, CTX))
                attempt = await timed(start_times, service.start(attempt, auth, CTX))
                attempt_ids.append(attempt.public_id)
        async with sessionmaker() as db:
            paper = await AttemptService(db, settings, redis).paper(attempt.public_id, attempt.id)
        for question in paper:
            async with gate:
                async with sessionmaker() as db:
                    saved = await timed(
                        save_times,
                        AnswerService(db, settings, redis).save(student, attempt.public_id, [AnswerItem(int(question["question_id"]), {"selected": "b"}, 1)]),
                    )
                    assert saved[0].status == "saved"
        async with gate:
            async with sessionmaker() as db:
                service = AttemptService(db, settings, redis)
                await service.submit(await service.get(attempt.public_id), reason=SubmitReason.MANUAL)

    started = time.perf_counter()
    await asyncio.gather(*(student_session(student) for student in students))
    session_seconds = time.perf_counter() - started
    saves = len(save_times)

    started = time.perf_counter()
    while await flush_answers(sessionmaker, redis, settings):
        pass
    flush_seconds = time.perf_counter() - started

    started = time.perf_counter()
    graded = 0
    while True:
        claimed = await grade_submitted(sessionmaker, redis, settings)
        if not claimed:
            break
        graded += claimed
    grade_seconds = time.perf_counter() - started

    async with sessionmaker() as db:
        done = (await db.execute(select(func.count()).select_from(Attempt).where(Attempt.status == "graded"))).scalar_one()
        depth = await GradingService(db, settings, redis).queue_depth()

    print(f"\n{args.students} students x {args.questions} questions  (PostgreSQL, fake Redis, one process, {args.concurrency} concurrent)")
    print(f"  whole sessions      {session_seconds:6.1f} s   ({args.students / session_seconds:.0f} students/s end to end)")
    print(f"  prepare attempt     {percentiles(prepare_times)}")
    print(f"  start attempt       {percentiles(start_times)}")
    print(f"  save one answer     {percentiles(save_times)}   ({saves / session_seconds:.0f} saves/s while sessions ran)")
    print(f"  flush to database   {flush_seconds:6.2f} s   ({saves / max(flush_seconds, 1e-9):.0f} answers/s)")
    print(f"  grade attempts      {grade_seconds:6.2f} s   ({graded / max(grade_seconds, 1e-9):.0f} attempts/s, {graded * args.questions / max(grade_seconds, 1e-9):.0f} answers/s)")
    print(f"  graded {done}/{args.students}; queue {depth}")
    await engine.dispose()
    if server is not None:
        server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
