"""AI resume shortlisting (docs/PRODUCT.md §5.7): rank applicants against the job, with reasons and red flags.

Run by the worker for each new application. The result is a **recommendation** — shortlist, review or reject — stored on the application
and logged in ``ai_decisions`` with the model and prompt version, so it can be audited and checked for bias. Nothing here moves an
application towards rejection: the only status change is ``applied → ai_screened``, and the state machine forbids the system to reject.

If ai-gateway cannot answer (quota, outage, moderation, an unparseable reply) the rule-based result stands alone and says so.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.gateway import GatewayClient, GatewayError
from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.core.time import utcnow
from app.domain.enums import Actor, ApplicationStatus, DecisionKind
from app.matching.model import Candidate
from app.matching.scoring import required_coverage
from app.models.application import AiDecision, Application
from app.models.job import Job
from app.screening import rules
from app.services.application_service import ApplicationService
from app.services.candidate_service import CandidateService, to_candidate
from app.services.job_service import JobService
from app.services.outbox import write_event


class ScreeningService:
    def __init__(self, db: AsyncSession, settings: Settings, gateway: GatewayClient | None) -> None:
        self.db = db
        self.settings = settings
        self.gateway = gateway

    async def screen(self, application_public_id: int) -> bool:
        """Screen one application. Returns False when there was nothing to do (already screened, withdrawn, gone)."""
        applications = ApplicationService(self.db, self.settings)
        try:
            application = await applications.get(application_public_id)
        except NotFoundError:
            return False  # a deleted application has nothing to screen
        if application.screened_at is not None or application.status != ApplicationStatus.APPLIED:
            return False
        job = await applications.job_of(application)
        jobs = JobService(self.db, self.settings)
        spec = await jobs.spec(job)
        candidates = CandidateService(self.db)
        profile = await candidates.profile(application.user_id)
        candidate = to_candidate(profile) if profile else Candidate(user_id=application.user_id, organization_id=application.organization_id)
        courses = await candidates.course_titles(None)
        matched, total = required_coverage(spec, candidate, courses)
        flags = rules.red_flags(spec, candidate, application.resume_snapshot, matched_required=matched, total_required=total)
        rule_score = rules.screening_score(application.match_score or 0, flags)
        payload = rules.anonymised_input(spec, candidate, courses, application.resume_snapshot, list(application.match_explanation or []))
        employer_org, job_title, application_id = job.employer_org_id, job.title, application.id
        await self.db.commit()  # nothing is held open across the model call

        ai = await self._ask_model(employer_org, job_title, payload) if self.settings.SCREEN_AI_ENABLED and self.gateway is not None else None

        application = await applications._locked(await applications.get(application_public_id))
        if application.screened_at is not None or application.status != ApplicationStatus.APPLIED:
            return False  # withdrawn or screened by another worker while the model thought
        if ai is not None:
            parsed, call = ai
            score = round((rule_score + parsed["score"]) / 2)
            reasons = [*parsed["reasons"], *(application.match_explanation or [])][:6]
            all_flags = list(dict.fromkeys([*flags, *parsed["red_flags"]]))
            source = "ai"
        else:
            parsed, call = None, None
            score, reasons, all_flags, source = rule_score, list(application.match_explanation or [])[:6], flags, "rules"
        recommendation = rules.recommend(score, shortlist_at=self.settings.SCREEN_SHORTLIST_DEFAULT_THRESHOLD, reject_below=self.settings.SCREEN_REJECT_BELOW)
        application.screen_score, application.screen_reasons, application.screen_red_flags = score, reasons, all_flags
        application.screen_source, application.screen_recommendation, application.screened_at = source, recommendation, utcnow()
        self.db.add(
            AiDecision(
                job_id=application.job_id, application_id=application.id, kind=DecisionKind.SCREENING, source=source, model=call.model if call else None,
                prompt_key="jobs.screen" if call else None, prompt_version=call.prompt_version if call else None, ai_call_id=call.call_id if call else None,
                input_digest=rules.digest(payload), input=payload, output={"rules_score": rule_score, "red_flags": flags, "ai": parsed, "final_score": score}, score=score,
                recommendation=recommendation,
            )
        )
        await applications.move(application, ApplicationStatus.AI_SCREENED, Actor.SYSTEM, actor_user_id=None, note=f"Screened ({source}): {recommendation}", job=job, locked=True)
        write_event(
            self.db, event_type="application.screened", aggregate_type="application", aggregate_id=application_id,
            payload={
                "application_id": str(application.public_id), "job_id": str(job.public_id), "employer_id": str(job.employer_org_id), "score": score, "recommendation": recommendation,
                "source": source, "occurred_at": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
        await self.db.commit()
        return True

    async def _ask_model(self, employer_org_id: int, job_title: str, payload: dict[str, Any]) -> tuple[dict[str, Any], Any] | None:
        if self.gateway is None:
            return None
        try:
            done = await self.gateway.complete(
                organization_id=employer_org_id, user_id=None, prompt_key="jobs.screen", variables={"job_title": job_title[:160]},
                messages=[{"role": "user", "content": rules.user_message(payload)}],
            )
        except GatewayError:
            return None
        if done.status != "ok":
            return None
        parsed = rules.parse_ai(done.content)
        return (parsed, done) if parsed is not None else None

    # ------------------------------------------------------------------ what a recruiter reads
    async def ranking(self, job: Job, *, shortlist_at: int, reject_below: int) -> dict[str, Any]:
        """The screened applicants still waiting for a decision, best first, bucketed by the recruiter's thresholds. Recommendations only."""
        rows = list(
            (
                await self.db.execute(
                    select(Application)
                    .where(Application.job_id == job.id, Application.status.in_([ApplicationStatus.APPLIED, ApplicationStatus.AI_SCREENED]))
                    .order_by(Application.screen_score.desc().nullslast(), Application.created_at)
                )
            ).scalars()
        )
        buckets: dict[str, list[Application]] = {"shortlist": [], "review": [], "reject": [], "unscreened": []}
        for application in rows:
            if application.screen_score is None:
                buckets["unscreened"].append(application)
            else:
                buckets[rules.recommend(application.screen_score, shortlist_at=shortlist_at, reject_below=reject_below)].append(application)
        return {"buckets": buckets, "shortlist_at": shortlist_at, "reject_below": reject_below}

    async def decisions(self, job: Job, *, page: int, per_page: int) -> list[AiDecision]:
        return list(
            (await self.db.execute(select(AiDecision).where(AiDecision.job_id == job.id).order_by(AiDecision.created_at.desc()).limit(per_page).offset((page - 1) * per_page))).scalars()
        )
