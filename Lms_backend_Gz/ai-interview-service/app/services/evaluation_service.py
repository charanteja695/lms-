"""Evaluating a finished interview (docs/PRODUCT.md §5.8 "Evaluation"): per-round rubric scores with evidence quotes and timestamps, and an overall
recommendation — computed here from the scores (app/evaluation/rubric.py), never chosen by the model — for a person to review.

Run by the worker for each completed interview. A model that is down is retried with backoff; one that keeps failing leaves the evaluation ``failed``
(visible to the recruiter, who can ask for a re-run). A candidate who answered nothing is not sent to the model at all.
"""

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.errors import Unavailable
from app.clients.gateway import Completion, GatewayClient, GatewayError
from app.core.config import Settings
from app.core.exceptions import ConflictError
from app.core.time import utcnow
from app.domain.enums import EvaluationStatus, InterviewStatus, PlanKind, Speaker, TurnKind, WorkKind
from app.evaluation import rubric
from app.models.interview import Evaluation, Interview, InterviewTurn
from app.services import work_service
from app.services.interview_service import InterviewService
from app.services.outbox import write_event


def _clock(ms: int) -> str:
    seconds = ms // 1000
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def transcript_dicts(turns: list[InterviewTurn]) -> list[dict[str, Any]]:
    return [{"seq": t.seq, "speaker": t.speaker, "kind": t.kind, "round": t.round_key, "text": t.text, "elapsed_ms": t.elapsed_ms} for t in turns]


def transcript_text(turns: list[dict[str, Any]]) -> str:
    """The transcript as the model reads it: one numbered line per turn, so a quote can be tied to a turn and a moment."""
    lines = []
    for t in turns:
        if t["kind"] == TurnKind.CODE:
            lines.append(f"[turn {t['seq']} | {_clock(t['elapsed_ms'])} | {t['round']} | candidate ran code]\n{t['text']}")
        elif t["kind"] == TurnKind.CODE_RESULT:
            lines.append(f"[turn {t['seq']} | {_clock(t['elapsed_ms'])} | {t['round']} | compiler output]\n{t['text']}")
        elif t["kind"] == TurnKind.NOTE and t["speaker"] == Speaker.SYSTEM:
            lines.append(f"[turn {t['seq']} | {_clock(t['elapsed_ms'])} | note] {t['text']}")
        else:
            lines.append(f"[turn {t['seq']} | {_clock(t['elapsed_ms'])} | {t['round']} | {t['speaker']}] {t['text']}")
    return "\n".join(lines)


def rounds_text(plan: dict[str, Any]) -> str:
    return "\n".join(f"- {r['key']} ({r['type']}): criteria {', '.join(r['criteria'])}" for r in plan["rounds"])


class EvaluationService:
    def __init__(self, db: AsyncSession, settings: Settings, gateway: GatewayClient | None) -> None:
        self.db = db
        self.settings = settings
        self.gateway = gateway
        self.interviews = InterviewService(db, settings)

    async def for_interview(self, interview: Interview) -> Evaluation | None:
        return (await self.db.execute(select(Evaluation).where(Evaluation.interview_id == interview.id))).scalar_one_or_none()

    # ------------------------------------------------------------------ scoring a transcript (also used by calibration)
    async def score_transcript(self, plan: dict[str, Any], turns: list[dict[str, Any]], *, billing_org: int, integrity_invalidated: bool = False) -> tuple[rubric.Evaluated, Completion, str]:
        """Ask the model to score ``turns`` against ``plan`` and verify what it says. Raises ``Unavailable`` when the model cannot give a usable answer."""
        if self.gateway is None:
            raise Unavailable("no ai-gateway configured")
        message = f"ROUNDS:\n{rounds_text(plan)}\n\nTRANSCRIPT:\n{transcript_text(turns)}"
        try:
            done = await self.gateway.complete(
                organization_id=billing_org, user_id=None, prompt_key="interview.evaluate", variables={"role": plan["role"][:120], "difficulty": plan["difficulty"]},
                messages=[{"role": "user", "content": message}], max_tokens=self.settings.EVAL_MAX_TOKENS,
            )
        except GatewayError as exc:
            raise Unavailable(f"ai-gateway: {exc}") from exc
        if done.status != "ok":
            raise Unavailable("the evaluation was blocked by moderation")
        data = rubric.parse(done.content)
        if data is None:
            raise Unavailable("the evaluator's answer was not in the expected shape")
        result = rubric.verify(
            data, plan=plan, turns=turns, min_evidence=self.settings.MIN_EVIDENCE_FOR_EXTREME_SCORE,
            thresholds=(self.settings.STRONG_YES_AT, self.settings.YES_AT, self.settings.LEAN_NO_AT), integrity_invalidated=integrity_invalidated,
        )
        return result, done, hashlib.sha256(message.encode()).hexdigest()

    # ------------------------------------------------------------------ evaluating an interview
    async def evaluate(self, interview_public_id: int, *, force: bool = False) -> bool:
        """Evaluate one interview. Returns False when there was nothing to do. Raises ``Unavailable`` to have the worker retry."""
        interview = await self.interviews.get(interview_public_id)
        existing = await self.for_interview(interview)
        if existing is not None and existing.status == EvaluationStatus.FINAL and not force:
            return False
        if interview.status not in {InterviewStatus.COMPLETED, InterviewStatus.EVALUATED, InterviewStatus.REVIEWED} or (interview.status != InterviewStatus.COMPLETED and not force):
            return False
        turns = transcript_dicts(await self.interviews.turns(interview))
        plan = interview.plan_snapshot
        billing = interview.employer_org_id or interview.organization_id or self.settings.PLATFORM_ORGANIZATION_ID
        integrity_invalidated = interview.integrity_status == "invalidated"
        answered = any(t["speaker"] == Speaker.CANDIDATE and t["kind"] == TurnKind.ANSWER for t in turns)
        await self.db.commit()  # nothing is held open across the model call
        call: Completion | None = None
        digest = None
        if answered:
            try:
                result, call, digest = await self.score_transcript(plan, turns, billing_org=billing, integrity_invalidated=integrity_invalidated)
            except Unavailable as exc:
                await self._note_failure(interview_public_id, str(exc))
                raise
        else:
            result = rubric.Evaluated(flags=["The candidate did not answer any question, so there is nothing to score."])
        improvement_plan = await self._feedback(interview, result) if interview.kind == PlanKind.MOCK and answered else None
        await self._store(interview_public_id, result, call, digest, improvement_plan)
        return True

    async def _note_failure(self, interview_public_id: int, error: str) -> None:
        interview = await self.interviews.get(interview_public_id)
        evaluation = await self.for_interview(interview)
        if evaluation is None:
            evaluation = Evaluation(interview_id=interview.id, status=EvaluationStatus.PENDING)
            self.db.add(evaluation)
        evaluation.last_error = error[:300]
        await self.db.commit()

    async def mark_failed(self, interview_public_id: int, error: str) -> None:
        """The worker gave up: the evaluation is ``failed`` and the recruiter can ask for a re-run."""
        interview = await self.interviews.get(interview_public_id)
        evaluation = await self.for_interview(interview)
        if evaluation is None:
            evaluation = Evaluation(interview_id=interview.id)
            self.db.add(evaluation)
        evaluation.status, evaluation.last_error = EvaluationStatus.FAILED, error[:300]
        await self.db.commit()

    async def _feedback(self, interview: Interview, result: rubric.Evaluated) -> str | None:
        """A candidate-facing improvement plan for a practice interview. Best effort: without it the report still lists strengths and improvements."""
        if self.gateway is None:
            return None
        notes = json.dumps({"criterion_scores": result.criterion_scores, "strengths": result.strengths, "improvements": result.improvements, "summary": result.summary})
        try:
            done = await self.gateway.complete(
                organization_id=interview.organization_id or self.settings.PLATFORM_ORGANIZATION_ID, user_id=interview.user_id, prompt_key="interview.feedback",
                variables={"role": interview.plan_snapshot["role"][:120]}, messages=[{"role": "user", "content": notes}],
            )
        except GatewayError:
            return None
        return done.content.strip()[:1500] if done.status == "ok" and done.content.strip() else None

    async def _store(self, interview_public_id: int, result: rubric.Evaluated, call: Completion | None, digest: str | None, improvement_plan: str | None) -> None:
        interview = await self.interviews.locked(await self.interviews.get(interview_public_id))
        evaluation = await self.for_interview(interview)
        if evaluation is None:
            evaluation = Evaluation(interview_id=interview.id)
            self.db.add(evaluation)
        evaluation.status, evaluation.last_error = EvaluationStatus.FINAL, None
        evaluation.model, evaluation.prompt_key, evaluation.prompt_version = (call.model if call else None), ("interview.evaluate" if call else None), (call.prompt_version if call else None)
        evaluation.ai_call_id, evaluation.input_digest = (call.call_id if call else None), digest
        evaluation.rounds, evaluation.criterion_scores, evaluation.overall_score, evaluation.recommendation = result.rounds, result.criterion_scores, result.overall, result.recommendation
        evaluation.summary, evaluation.strengths, evaluation.improvements, evaluation.flags = result.summary, result.strengths, result.improvements, result.flags
        evaluation.invalid_quotes, evaluation.total_quotes, evaluation.improvement_plan = result.invalid_quotes, result.total_quotes, improvement_plan
        if interview.status == InterviewStatus.COMPLETED:
            interview.status = InterviewStatus.EVALUATED
        if interview.kind == PlanKind.MOCK:
            interview.feedback_released = True  # practice: the candidate reads the report at once
        await self.db.flush()
        payload = {
            "interview_id": str(interview.public_id), "plan_id": str(interview.plan_id), "kind": interview.kind, "user_id": str(interview.user_id), "recommendation": evaluation.recommendation,
            "score": evaluation.overall_score, "occurred_at": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        write_event(self.db, event_type="interview.evaluated", aggregate_type="interview", aggregate_id=interview.id, payload=payload)
        if interview.kind == PlanKind.SCREENING and interview.application_id:
            # the contract job-portal-service consumes: it completes the application's interview stage and shows the recruiter the report
            write_event(
                self.db, event_type="interview.completed", aggregate_type="interview", aggregate_id=interview.id,
                payload={
                    **payload, "application_id": str(interview.application_id), "job_id": str(interview.job_id) if interview.job_id else None, "employer_id": str(interview.employer_org_id) if interview.employer_org_id else None,
                    "report": {
                        "summary": evaluation.summary, "criterion_scores": evaluation.criterion_scores, "strengths": evaluation.strengths, "improvements": evaluation.improvements, "flags": evaluation.flags,
                        "attempt_no": interview.attempt_no,
                    },
                },
            )
        await self.db.commit()

    async def rerun(self, interview: Interview) -> None:
        """A recruiter asks for an evaluation to be run again (after a failure, or with a newer prompt)."""
        if interview.status not in {InterviewStatus.COMPLETED, InterviewStatus.EVALUATED, InterviewStatus.REVIEWED}:
            raise ConflictError("Only a finished interview can be evaluated.", code="INVALID_STATE")
        await work_service.enqueue(self.db, WorkKind.EVALUATE, interview.public_id, {"force": True})
        await self.db.commit()

