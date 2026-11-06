"""A student's practice interview end to end: quota, consent, the server's clock, the director choosing what is asked next, a coding round,
evaluation and the candidate's own report — which never carries the recommendation (docs/PRODUCT.md §5.8)."""

import json
from datetime import timedelta

from sqlalchemy import select

from app.core.time import utcnow
from app.models.interview import Interview
from app.services.interview_service import InterviewService
from tests.conftest import API, EMPLOYER, INSTITUTION, RECRUITER, STUDENT, create_published_plan, round_body


def evaluate_reply(rounds: dict[str, dict[str, tuple[int, str]]], *, summary: str = "A solid interview.") -> str:
    """A well-formed ``interview.evaluate`` completion: one quote per criterion, taken verbatim from the candidate's own answers."""
    return json.dumps(
        {
            "rounds": [
                {"round": key, "comment": "Handled well.", "scores": {c: {"score": score, "evidence": [{"quote": quote}]} for c, (score, quote) in criteria.items()}}
                for key, criteria in rounds.items()
            ],
            "summary": summary, "strengths": ["Clear communication"], "improvements": ["Could go deeper on trade-offs"],
        }
    )


async def _create_mock_plan(client, who) -> str:
    rounds = [round_body(type_="intro", minutes=5, questions=("Tell me about yourself.",)), round_body(type_="technical", minutes=10, questions=("Describe a system you built.",))]
    return await create_published_plan(client, who, kind="mock", rounds=rounds, duration_minutes=15)


async def test_the_monthly_quota_and_one_open_interview_rule(client, who, settings):
    plan_id = await _create_mock_plan(client, who)
    for _ in range(settings.MOCK_INTERVIEWS_PER_MONTH):
        interview_id = await _start(client, who, plan_id)
        who.student()
        ended = await client.post(f"{API}/student/interviews/{interview_id}/end")
        assert ended.status_code == 200, ended.text

    who.student()
    over_quota = await client.post(f"{API}/student/interviews", json={"plan_id": plan_id})
    assert over_quota.status_code == 429 and over_quota.json()["code"] == "MOCK_QUOTA_EXCEEDED"


async def test_only_one_open_practice_interview_at_a_time(client, who):
    plan_id = await _create_mock_plan(client, who)
    who.student()
    first = await client.post(f"{API}/student/interviews", json={"plan_id": plan_id})
    assert first.status_code == 201
    second = await client.post(f"{API}/student/interviews", json={"plan_id": plan_id})
    assert second.status_code == 409 and second.json()["code"] == "INTERVIEW_ALREADY_OPEN"


async def test_consent_must_match_the_current_version_and_recording_when_proctored(client, who):
    plan_id = await _create_mock_plan(client, who)
    who.student()
    interview_id = (await client.post(f"{API}/student/interviews", json={"plan_id": plan_id})).json()["interview"]["interview_id"]

    stale = await client.post(f"{API}/student/interviews/{interview_id}/consent", json={"version": "2020-01", "recording": True})
    assert stale.status_code == 409 and stale.json()["code"] == "CONSENT_VERSION_CHANGED"

    consent = await client.get(f"{API}/student/interviews/{interview_id}/consent")
    ok = await client.post(f"{API}/student/interviews/{interview_id}/consent", json={"version": consent.json()["consent"]["version"], "recording": False})
    assert ok.status_code == 200


async def test_starting_without_consent_is_refused(client, who):
    plan_id = await _create_mock_plan(client, who)
    who.student()
    interview_id = (await client.post(f"{API}/student/interviews", json={"plan_id": plan_id})).json()["interview"]["interview_id"]
    response = await client.post(f"{API}/student/interviews/{interview_id}/start")
    assert response.status_code == 409 and response.json()["code"] == "CONSENT_REQUIRED"


async def _start(client, who, plan_id: str) -> str:
    who.student()
    interview_id = (await client.post(f"{API}/student/interviews", json={"plan_id": plan_id})).json()["interview"]["interview_id"]
    consent = await client.get(f"{API}/student/interviews/{interview_id}/consent")
    await client.post(f"{API}/student/interviews/{interview_id}/consent", json={"version": consent.json()["consent"]["version"], "recording": False})
    started = await client.post(f"{API}/student/interviews/{interview_id}/start")
    assert started.status_code == 200, started.text
    return interview_id


async def test_a_full_interview_is_evaluated_and_the_candidates_report_never_shows_the_recommendation(client, who, gateway, work):
    plan_id = await _create_mock_plan(client, who)
    interview_id = await _start(client, who, plan_id)
    who.student()

    intro_answer = "My name is Asha and I have built production backend systems for two years using Python."
    technical_answer = "I designed a horizontally scalable REST API in FastAPI backed by PostgreSQL to serve real-time inventory updates."
    gateway.reply_follow_up(None)  # after the intro answer: no follow-up, so the director moves to the next round
    gateway.reply_follow_up(None)  # after the technical answer: the interview is finished (it was the last round's only question)

    first = await client.post(f"{API}/student/interviews/{interview_id}/turns", json={"text": intro_answer})
    assert first.status_code == 200, first.text
    assert first.json()["turns"]["reply"]["round"] == "technical_1"

    second = await client.post(f"{API}/student/interviews/{interview_id}/turns", json={"text": technical_answer})
    assert second.status_code == 200, second.text
    assert second.json()["turns"]["finished"] is True

    gateway.reply(
        evaluate_reply(
            {
                "intro_1": {"communication": (5, intro_answer[:30])},
                "technical_1": {"technical_depth": (5, technical_answer[:30]), "problem_solving": (4, technical_answer[10:40]), "communication": (4, technical_answer[:30])},
            }
        )
    )
    worked = await work()
    assert worked == 1

    report = await client.get(f"{API}/student/interviews/{interview_id}/report")
    assert report.status_code == 200
    body = report.json()["report"]
    assert body["released"] is True
    assert "recommendation" not in body
    assert body["summary"] == "A solid interview." and body["improvement_plan"]  # a mock interview gets a candidate-facing improvement plan
    assert 0 < body["criterion_scores"]["technical_depth"] <= 5
    assert 1 <= body["overall_score"] <= body["score_max"] == 5
    technical = next(r for r in body["rounds"] if r["round"] == "technical_1")
    assert technical["score"] and technical["quotes"] and all(q for q in technical["quotes"])
    listed = (await client.get(f"{API}/student/interviews")).json()["interviews"]
    assert next(i for i in listed if i["interview_id"] == interview_id)["overall_score"] == body["overall_score"]


async def test_a_follow_up_the_model_proposes_is_asked_next(client, who, gateway):
    plan_id = await _create_mock_plan(client, who)
    interview_id = await _start(client, who, plan_id)
    who.student()
    gateway.reply_follow_up("What was the hardest bug you fixed on that project?")
    turn = await client.post(f"{API}/student/interviews/{interview_id}/turns", json={"text": "I shipped a payments feature end to end."})
    assert turn.status_code == 200
    reply = turn.json()["turns"]["reply"]
    assert reply["kind"] == "follow_up" and "hardest bug" in reply["text"]


async def test_when_the_model_cannot_answer_the_turn_is_degraded_but_the_interview_continues(client, who, gateway):
    plan_id = await _create_mock_plan(client, who)
    interview_id = await _start(client, who, plan_id)
    who.student()
    gateway.completion_error = (500, "UPSTREAM_ERROR")
    turn = await client.post(f"{API}/student/interviews/{interview_id}/turns", json={"text": "My first answer to the intro question."})
    assert turn.status_code == 200
    assert turn.json()["turns"]["degraded"] is True
    assert turn.json()["turns"]["reply"]["round"] == "technical_1"  # moved straight to the next core question


async def test_the_same_idempotency_key_replays_the_same_turn(client, who, gateway):
    plan_id = await _create_mock_plan(client, who)
    interview_id = await _start(client, who, plan_id)
    who.student()
    gateway.reply_follow_up(None)
    headers = {"Idempotency-Key": "turn-retry-attempt-1"}
    first = await client.post(f"{API}/student/interviews/{interview_id}/turns", json={"text": "Answering the intro question."}, headers=headers)
    assert first.status_code == 200
    replay = await client.post(f"{API}/student/interviews/{interview_id}/turns", json={"text": "Answering the intro question."}, headers=headers)
    assert replay.status_code == 200
    assert replay.json()["turns"]["turn"]["seq"] == first.json()["turns"]["turn"]["seq"]
    assert len(gateway.completions) == 1  # the model was never asked twice for the same turn


async def test_speech_to_text_unavailable_tells_the_candidate_to_type(client, who, gateway):
    plan_id = await _create_mock_plan(client, who)
    interview_id = await _start(client, who, plan_id)
    who.student()
    gateway.stt_available = False
    response = await client.post(f"{API}/student/interviews/{interview_id}/turns/audio", files={"audio": ("answer.webm", b"fake-bytes", "audio/webm")})
    assert response.status_code == 503 and response.json()["code"] == "SPEECH_UNAVAILABLE"


async def test_running_code_only_works_in_the_coding_round(client, who, codeexec):
    rounds = [round_body(type_="intro", minutes=5, questions=("Tell me about yourself.",)), round_body(type_="coding", minutes=15, languages=("python",))]
    plan_id = await create_published_plan(client, who, kind="mock", rounds=rounds, duration_minutes=20)
    interview_id = await _start(client, who, plan_id)
    who.student()
    refused = await client.post(f"{API}/student/interviews/{interview_id}/code/run", json={"language": "python", "source": "print('hi')"})
    assert refused.status_code == 409 and refused.json()["code"] == "NOT_CODING_ROUND"


async def test_a_code_run_is_recorded_in_the_transcript(client, who, gateway, codeexec):
    rounds = [round_body(type_="coding", minutes=15, questions=("Write a function that reverses a string.",), languages=("python",))]
    plan_id = await create_published_plan(client, who, kind="mock", rounds=rounds, duration_minutes=15)
    interview_id = await _start(client, who, plan_id)
    who.student()
    codeexec.stdout = "olleh\n"
    run = await client.post(f"{API}/student/interviews/{interview_id}/code/run", json={"language": "python", "source": "print('hello'[::-1])"})
    assert run.status_code == 200, run.text
    result = run.json()["run"]
    assert result["stdout"] == "olleh\n" and result["code"]["kind"] == "code" and result["result"]["kind"] == "code_result"
    assert len(codeexec.runs) == 1


async def test_time_up_ends_the_interview_and_the_sweep_catches_a_stale_one(client, who, sessionmaker, settings):
    plan_id = await create_published_plan(
        client, who, kind="mock", rounds=[round_body(type_="intro", minutes=3, questions=("Tell me about yourself.",))], duration_minutes=10,
    )
    interview_id = await _start(client, who, plan_id)
    who.student()

    async with sessionmaker() as db:
        row = (await db.execute(select(Interview).where(Interview.public_id == int(interview_id)))).scalar_one()
        row.ends_at = utcnow() - timedelta(seconds=settings.OVERRUN_GRACE_SECONDS + 5)
        await db.commit()

    async with sessionmaker() as db:
        ended, expired = await InterviewService(db, settings).close_stale()
        assert ended == 1 and expired == 0

    status = await client.get(f"{API}/student/interviews/{interview_id}")
    assert status.json()["interview"]["status"] == "completed"


async def test_a_candidate_can_reload_the_conversation_so_far_and_nobody_else_can(client, who, gateway):
    plan_id = await _create_mock_plan(client, who)
    interview_id = await _start(client, who, plan_id)
    who.student()
    gateway.reply_follow_up(None)
    await client.post(f"{API}/student/interviews/{interview_id}/turns", json={"text": "I build data pipelines."})
    turns = (await client.get(f"{API}/student/interviews/{interview_id}/transcript")).json()["turns"]
    speakers = [t["speaker"] for t in turns]
    assert speakers[0] == "interviewer" and "candidate" in speakers
    assert any(t["text"] == "I build data pipelines." for t in turns)
    assert [t["seq"] for t in turns] == sorted(t["seq"] for t in turns)
    current = (await client.get(f"{API}/student/interviews/{interview_id}")).json()["interview"]["current_round"]
    # the one intro question is answered, so the interview has moved on to the technical round — the round of its latest question
    assert (current["type"], current["number"], current["total"]) == ("technical", 2, 2) and current["key"] == turns[-1]["round"]
    who.student(user_id=1755000000999999)
    assert (await client.get(f"{API}/student/interviews/{interview_id}/transcript")).status_code == 404


async def test_interviews_follow_the_persons_permissions(client, act_as):
    """A super admin can take interviews away from one student, or screening away from one recruiter."""
    act_as(STUDENT, role="student", organization_id=INSTITUTION, defaults=False)
    assert (await client.get(f"{API}/student/interviews")).status_code == 403
    act_as(RECRUITER, role="recruiter", organization_id=EMPLOYER, defaults=False)
    assert (await client.get(f"{API}/employer/interviews")).status_code == 403
    act_as(RECRUITER, role="recruiter", organization_id=EMPLOYER)
    assert (await client.get(f"{API}/employer/interviews")).status_code == 200
