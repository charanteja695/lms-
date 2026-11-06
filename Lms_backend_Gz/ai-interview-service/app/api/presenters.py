"""Turn rows into response objects, so every endpoint shows an interview, a turn or an evaluation the same way, and a candidate never
sees what only a recruiter or careers manager may (the AI's recommendation, the transcript before the interview is theirs to read)."""

from app.evaluation import rubric
from app.models.calibration import CalibrationRun, CalibrationSample
from app.models.interview import Appeal, Evaluation, Interview, InterviewTurn
from app.models.plan import InterviewPlan
from app.schemas.calibration import CalibrationRunOut, CalibrationSampleOut
from app.schemas.interview import (
    AppealOut,
    CurrentRoundOut,
    EmployerInterviewDetail,
    EmployerInterviewOut,
    EvaluationOut,
    InterviewOut,
    ReportOut,
    TurnOut,
)
from app.schemas.plan import PlanOut


def plan_out(plan: InterviewPlan) -> PlanOut:
    return PlanOut(
        plan_id=plan.public_id, family_id=plan.family_id, version=plan.version, owner_org_id=plan.owner_org_id, kind=plan.kind, title=plan.title, role=plan.role, skills=list(plan.skills or []),
        difficulty=plan.difficulty, duration_minutes=plan.duration_minutes, rounds=plan.rounds, criteria_weights=plan.criteria_weights, instructions=plan.instructions,
        proctoring_level=plan.proctoring_level, max_attempts=plan.max_attempts, retake_cooldown_days=plan.retake_cooldown_days, status=plan.status, published_at=plan.published_at, created_at=plan.created_at,
    )


def turn_out(turn: InterviewTurn) -> TurnOut:
    return TurnOut(seq=turn.seq, round=turn.round_key, speaker=turn.speaker, kind=turn.kind, text=turn.text, elapsed_ms=turn.elapsed_ms, via=turn.via, meta=turn.meta)


def interview_out(interview: Interview) -> InterviewOut:
    snapshot = interview.plan_snapshot
    return InterviewOut(
        interview_id=interview.public_id, plan_id=interview.plan_id, kind=interview.kind, status=interview.status, attempt_no=interview.attempt_no, role=snapshot.get("role", ""),
        duration_minutes=int(snapshot.get("duration_minutes", 0)), invite_expires_at=interview.invite_expires_at, started_at=interview.started_at, ends_at=interview.ends_at,
        completed_at=interview.completed_at, round_index=interview.round_index, turn_count=interview.turn_count, code_runs=interview.code_runs, feedback_released=interview.feedback_released,
        retake_granted=interview.retake_granted, created_at=interview.created_at, current_round=_current_round(interview),
    )


def _current_round(interview: Interview) -> CurrentRoundOut | None:
    rounds = interview.plan_snapshot.get("rounds") or []
    if not rounds:
        return None
    index = min(interview.round_index, len(rounds) - 1)
    r = rounds[index]
    return CurrentRoundOut(key=r["key"], type=r["type"], minutes=int(r["minutes"]), languages=list(r.get("languages") or []), number=index + 1, total=len(rounds))


def employer_interview_out(interview: Interview) -> EmployerInterviewOut:
    snapshot = interview.plan_snapshot
    return EmployerInterviewOut(
        interview_id=interview.public_id, plan_id=interview.plan_id, kind=interview.kind, status=interview.status, attempt_no=interview.attempt_no, role=snapshot.get("role", ""),
        duration_minutes=int(snapshot.get("duration_minutes", 0)), invite_expires_at=interview.invite_expires_at, started_at=interview.started_at, ends_at=interview.ends_at,
        completed_at=interview.completed_at, round_index=interview.round_index, turn_count=interview.turn_count, code_runs=interview.code_runs, feedback_released=interview.feedback_released,
        retake_granted=interview.retake_granted, created_at=interview.created_at, application_id=interview.application_id, job_id=interview.job_id, user_id=interview.user_id,
        integrity_status=interview.integrity_status, reviewed_by=interview.reviewed_by, reviewed_at=interview.reviewed_at, final_recommendation=interview.final_recommendation, review_note=interview.review_note,
    )


def evaluation_out(evaluation: Evaluation) -> EvaluationOut:
    return EvaluationOut(
        status=evaluation.status, model=evaluation.model, prompt_version=evaluation.prompt_version, rounds=evaluation.rounds, criterion_scores=evaluation.criterion_scores,
        overall_score=evaluation.overall_score, recommendation=evaluation.recommendation, summary=evaluation.summary, strengths=evaluation.strengths, improvements=evaluation.improvements,
        flags=evaluation.flags, invalid_quotes=evaluation.invalid_quotes, total_quotes=evaluation.total_quotes, last_error=evaluation.last_error,
    )


def employer_interview_detail(interview: Interview, turns: list[InterviewTurn], evaluation: Evaluation | None) -> EmployerInterviewDetail:
    base = employer_interview_out(interview)
    return EmployerInterviewDetail(**{k: getattr(base, k) for k in EmployerInterviewOut.model_fields}, transcript=[turn_out(t) for t in turns], evaluation=evaluation_out(evaluation) if evaluation else None)


def report_out(interview: Interview, evaluation: Evaluation | None) -> ReportOut:
    """The candidate's report: never the recommendation (docs/PRODUCT.md §5.8), and only once released."""
    if not interview.feedback_released or evaluation is None or evaluation.status != "final":
        return ReportOut(released=False)
    rounds = []
    for r in evaluation.rounds or []:
        scores = [s["score"] for s in (r.get("scores") or {}).values() if isinstance(s, dict) and isinstance(s.get("score"), int | float)]
        quotes = [e["quote"] for s in (r.get("scores") or {}).values() if isinstance(s, dict) for e in s.get("evidence") or []][:3]
        rounds.append({"round": r.get("round"), "type": r.get("type"), "score": round(sum(scores) / len(scores), 1) if scores else None, "comment": r.get("comment") or "", "quotes": quotes})
    return ReportOut(
        released=True, summary=evaluation.summary, criterion_scores=evaluation.criterion_scores, strengths=evaluation.strengths, improvements=evaluation.improvements,
        improvement_plan=evaluation.improvement_plan, overall_score=evaluation.overall_score, score_max=rubric.SCORE_MAX, rounds=rounds,
    )


def appeal_out(appeal: Appeal, interview_public_id: int) -> AppealOut:
    """``interview_public_id``: ``Appeal.interview_id`` is the interview's internal id, not the public one it is addressed by."""
    return AppealOut(
        appeal_id=appeal.public_id, interview_id=interview_public_id, user_id=appeal.user_id, reason=appeal.reason, status=appeal.status, decided_by=appeal.decided_by,
        decided_at=appeal.decided_at, decision_note=appeal.decision_note, created_at=appeal.created_at,
    )


def calibration_sample_out(sample: CalibrationSample) -> CalibrationSampleOut:
    return CalibrationSampleOut(sample_id=sample.public_id, human_scores=sample.human_scores, human_recommendation=sample.human_recommendation, rated_by=sample.rated_by, created_at=sample.created_at)


def calibration_run_out(run: CalibrationRun) -> CalibrationRunOut:
    return CalibrationRunOut(
        run_id=run.public_id, model=run.model, prompt_version=run.prompt_version, samples=run.samples, mean_abs_error=run.mean_abs_error, within_one_rate=run.within_one_rate,
        recommendation_agreement=run.recommendation_agreement, details=run.details, created_at=run.created_at,
    )
