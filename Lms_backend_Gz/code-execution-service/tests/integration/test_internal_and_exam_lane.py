from httpx import AsyncClient
from sqlalchemy import select

from app.domain.enums import Priority
from app.models.outbox_event import OutboxEvent
from app.models.run import Run
from app.models.submission import Submission
from app.services.queue_service import QueueService
from tests.conftest import INTERNAL_TOKEN, ORG_A, STUDENT, STUDENT_2, SUM_SOLUTION, ProblemFactory

V1 = "/api/v1"
TOKEN = {"X-Internal-Service-Token": INTERNAL_TOKEN}


def exam_body(problem_id: int, **extra: object) -> dict:
    return {
        "user_id": str(STUDENT), "organization_id": str(ORG_A), "problem_id": str(problem_id), "language": "python3",
        "source": SUM_SOLUTION, "reference": "attempt:1755000000009001", **extra,
    }


async def test_internal_endpoints_need_the_service_token_not_a_user_token(client: AsyncClient, make_problem: ProblemFactory, as_student, as_super_admin) -> None:
    problem_id = await make_problem()
    for sign_in in (as_student, as_super_admin):  # not even a super admin's access token is enough
        sign_in()
        for method, path in (("POST", "/internal/submissions"), ("GET", "/internal/submissions/1"), ("GET", "/internal/queue")):
            response = await client.request(method, f"{V1}{path}", json=exam_body(problem_id))
            assert (response.status_code, response.json()["code"]) == (403, "INTERNAL_CALLER_REQUIRED"), path
    wrong = await client.get(f"{V1}/internal/queue", headers={"X-Internal-Service-Token": "guess"})
    assert wrong.status_code == 403


async def test_assessment_submits_for_a_student_in_the_exam_lane(client: AsyncClient, make_problem: ProblemFactory, sessionmaker, judge_with, real_engine, drain) -> None:
    problem_id = await make_problem()
    created = await client.post(f"{V1}/internal/submissions", json=exam_body(problem_id), headers=TOKEN)
    assert created.status_code == 202
    submission = created.json()["submission"]
    assert (submission["user_id"], submission["organization_id"], submission["reference"]) == (str(STUDENT), str(ORG_A), "attempt:1755000000009001")
    async with sessionmaker() as db:
        assert (await db.execute(select(Submission.priority))).scalar_one() == Priority.EXAM

    await drain(judge_with(real_engine))
    judged = (await client.get(f"{V1}/internal/submissions/{submission['submission_id']}", headers=TOKEN)).json()["submission"]
    assert (judged["verdict"], judged["score"], judged["source"] == SUM_SOLUTION) == ("accepted", 100, True)

    async with sessionmaker() as db:
        [event] = (await db.execute(select(OutboxEvent))).scalars().all()
    assert (event.payload["reference"], event.payload["user_id"], event.payload["verdict"]) == ("attempt:1755000000009001", str(STUDENT), "accepted")


async def test_the_student_owns_an_exam_submission_made_for_them(client: AsyncClient, make_problem: ProblemFactory, as_student, judge_with, real_engine, drain) -> None:
    problem_id = await make_problem()
    sid = (await client.post(f"{V1}/internal/submissions", json=exam_body(problem_id), headers=TOKEN)).json()["submission"]["submission_id"]
    await drain(judge_with(real_engine))
    as_student(STUDENT)
    assert (await client.get(f"{V1}/submissions/{sid}")).json()["submission"]["verdict"] == "accepted"
    as_student(STUDENT_2)
    assert (await client.get(f"{V1}/submissions/{sid}")).status_code == 404


async def test_exam_work_is_served_before_practice_work_however_late_it_arrives(
    client: AsyncClient, make_problem: ProblemFactory, as_student, sessionmaker, settings
) -> None:
    problem_id = await make_problem()
    as_student()
    for _ in range(3):  # a queue of practice work, all submitted first
        await client.post(f"{V1}/runs", json={"language": "python3", "source": "print(1)"})
        await client.post(f"{V1}/problems/{problem_id}/submissions", json={"language": "python3", "source": SUM_SOLUTION})
    exam = (await client.post(f"{V1}/internal/submissions", json=exam_body(problem_id), headers=TOKEN)).json()["submission"]["submission_id"]

    async with sessionmaker() as db:
        first = await QueueService(db, settings).claim(Submission, 1)
    assert [str(job.public_id) for job in first] == [exam]  # the exam jumped four practice submissions

    async with sessionmaker() as db:
        rest = await QueueService(db, settings).claim(Submission, 10)
    assert [job.priority for job in rest] == [Priority.SUBMISSION] * 3  # then graded practice, in arrival order
    async with sessionmaker() as db:
        runs = await QueueService(db, settings).claim(Run, 10)
    assert [job.priority for job in runs] == [Priority.PRACTICE] * 3  # custom-input runs are the lowest lane


async def test_the_queue_depth_per_lane_is_the_autoscaling_signal(client: AsyncClient, make_problem: ProblemFactory, as_student) -> None:
    problem_id = await make_problem()
    as_student()
    await client.post(f"{V1}/runs", json={"language": "python3", "source": "print(1)"})
    await client.post(f"{V1}/runs", json={"language": "python3", "source": "print(2)"})
    await client.post(f"{V1}/problems/{problem_id}/submissions", json={"language": "python3", "source": SUM_SOLUTION})
    await client.post(f"{V1}/internal/submissions", json=exam_body(problem_id), headers=TOKEN)

    queue = (await client.get(f"{V1}/internal/queue", headers=TOKEN)).json()["queue"]
    assert queue == {"runs": {"0": 2}, "submissions": {"1": 1, "2": 1}}


async def test_internal_submissions_are_validated_and_idempotent(client: AsyncClient, make_problem: ProblemFactory) -> None:
    problem_id = await make_problem()
    draft = await make_problem(cases=[], publish=False)

    async def post(**overrides: object):
        body = {**exam_body(problem_id), **overrides}
        return await client.post(f"{V1}/internal/submissions", json=body, headers=TOKEN)

    assert (await post(problem_id=str(draft))).status_code == 404  # not a published problem
    assert (await post(language="klingon")).json()["details"][0]["code"] == "LANGUAGE_NOT_ALLOWED"
    assert (await post(priority=0)).status_code == 422  # lane 0 is for runs
    assert (await post(priority=7)).status_code == 422
    assert (await post(reference="")).status_code == 422
    body = exam_body(problem_id)
    del body["reference"]
    assert (await client.post(f"{V1}/internal/submissions", json=body, headers=TOKEN)).status_code == 422  # the attempt must be named

    keyed = {**TOKEN, "Idempotency-Key": "attempt-submit-1"}
    first = await client.post(f"{V1}/internal/submissions", json=exam_body(problem_id), headers=keyed)
    again = await client.post(f"{V1}/internal/submissions", json=exam_body(problem_id), headers=keyed)
    assert first.json()["submission"]["submission_id"] == again.json()["submission"]["submission_id"]  # a retried call judges once

    practice = await post(priority=1)
    assert practice.status_code == 202


async def test_a_flood_of_exam_submissions_is_not_rate_limited_by_the_student_limits(client: AsyncClient, app, settings, make_problem: ProblemFactory) -> None:
    from app.core.config import get_settings

    limited = settings.model_copy(update={"RATE_LIMIT_ENABLED": True, "SUBMISSION_RATE_LIMIT_PER_USER_PER_MINUTE": 1})
    app.dependency_overrides[get_settings] = lambda: limited
    problem_id = await make_problem()
    for n in range(4):  # assessment-service paces its own students
        response = await client.post(f"{V1}/internal/submissions", json=exam_body(problem_id, reference=f"attempt:{n}"), headers=TOKEN)
        assert response.status_code == 202


async def test_the_interviewer_runs_a_candidates_code_through_the_internal_endpoint(client: AsyncClient, sessionmaker, judge_with, real_engine, drain) -> None:
    body = {"user_id": str(STUDENT), "organization_id": str(ORG_A), "language": "python3", "source": "print(6 * 7)", "stdin": ""}
    assert (await client.post(f"{V1}/internal/runs", json=body)).status_code == 403  # the service token, not a user's
    created = await client.post(f"{V1}/internal/runs", json=body, headers=TOKEN)
    assert created.status_code == 202
    run = created.json()["run"]
    async with sessionmaker() as db:
        row = (await db.execute(select(Run))).scalar_one()
    assert (row.user_id, row.organization_id, row.priority) == (STUDENT, ORG_A, Priority.PRACTICE)
    await drain(judge_with(real_engine))
    done = (await client.get(f"{V1}/internal/runs/{run['run_id']}", headers=TOKEN)).json()["run"]
    assert (done["status"], done["outcome"], done["stdout"].strip()) == ("completed", "ok", "42")
    assert (await client.get(f"{V1}/internal/runs/1755000000099999", headers=TOKEN)).status_code == 404
    bad = await client.post(f"{V1}/internal/runs", json={**body, "language": "cobol"}, headers=TOKEN)
    assert bad.status_code in (404, 422)
