"""A proctored test starts only after proctoring-service has passed the student's pre-check (it publishes a Redis key)."""

from tests.conftest import MODULE, STUDENT, fixed, mcq


async def proctored(make_question, make_test, level="basic"):
    q1 = await make_question(mcq())
    return await make_test([fixed(q1)], kind="module", target_id=str(MODULE), proctoring_level=level)


async def test_a_proctored_test_cannot_start_without_a_passed_precheck(client, who, enroll, make_question, make_test, settings, redis):
    settings.PROCTORING_PRECHECK_REQUIRED = True
    test_id = await proctored(make_question, make_test)
    await enroll()
    who.student()
    blocked = await client.post(f"/api/v1/tests/{test_id}/attempts", json={"start_now": True})
    assert blocked.status_code == 409 and blocked.json()["code"] == "PROCTORING_PRECHECK_REQUIRED"

    # the paper can still be prepared; only the clock is gated
    attempt_id = (await client.post(f"/api/v1/tests/{test_id}/attempts", json={})).json()["attempt"]["attempt_id"]
    refused = await client.post(f"/api/v1/attempts/{attempt_id}/start")
    assert refused.status_code == 409 and refused.json()["code"] == "PROCTORING_PRECHECK_REQUIRED"

    await redis.set(f"lms:proctor:ready:{STUDENT}:{test_id}", "1", ex=600)  # proctoring-service: the pre-check passed
    started = await client.post(f"/api/v1/attempts/{attempt_id}/start")
    assert started.status_code == 200 and started.json()["attempt"]["status"] == "in_progress"


async def test_the_flag_is_per_student_and_per_test(client, who, enroll, make_question, make_test, settings, redis):
    settings.PROCTORING_PRECHECK_REQUIRED = True
    test_id = await proctored(make_question, make_test)
    await enroll()
    await redis.set(f"lms:proctor:ready:{STUDENT + 1}:{test_id}", "1")  # someone else's pre-check
    await redis.set(f"lms:proctor:ready:{STUDENT}:{int(test_id) + 1}", "1")  # another test's
    who.student()
    assert (await client.post(f"/api/v1/tests/{test_id}/attempts", json={"start_now": True})).status_code == 409


async def test_unproctored_tests_are_not_gated(client, who, enroll, make_question, make_test, settings):
    settings.PROCTORING_PRECHECK_REQUIRED = True
    q1 = await make_question(mcq())
    test_id = await make_test([fixed(q1)], kind="module", target_id=str(MODULE))
    await enroll()
    who.student()
    assert (await client.post(f"/api/v1/tests/{test_id}/attempts", json={"start_now": True})).status_code == 201


async def test_the_gate_can_be_switched_off(client, who, enroll, make_question, make_test, settings):
    settings.PROCTORING_PRECHECK_REQUIRED = False
    test_id = await proctored(make_question, make_test, "strict")
    await enroll()
    who.student()
    assert (await client.post(f"/api/v1/tests/{test_id}/attempts", json={"start_now": True})).status_code == 201
